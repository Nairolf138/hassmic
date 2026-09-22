"""Native Assist satellite bridge for HassMic.

This module is intentionally not added to PLATFORMS until the playback bridge
is enabled. Keeping it dormant prevents the legacy Wyoming entity and this
entity from owning the same microphone at the same time.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import contextlib
import logging
from uuid import uuid4

import betterproto
from homeassistant.components import tts
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineStage
from homeassistant.components.assist_satellite import (
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteWakeWord,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription

from . import util
from .proto.hassmic import (
    ClientEvent,
    WyomingEvent,
    WyomingEventAudioChunk,
    WyomingEventAudioStart,
    WyomingEventAudioStop,
    WyomingEventRunPipeline,
)

_LOGGER = logging.getLogger(__name__)


class HassMicNativeSatellite(AssistSatelliteEntity):
    """Own the HA Assist pipeline while HassMic owns the physical microphone."""

    entity_description = EntityDescription(key="native_assist_satellite")

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__()
        self.hass = hass
        self.config_entry = entry
        self.hassmic_entity_name = "native_assist_satellite"
        util.InitializeEntity(self, "assist_satellite.{}", hass, entry)
        self._hassmic = entry.runtime_data
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._turn_id: str | None = None
        self._pipeline_task: asyncio.Task[None] | None = None
        self._stopped = False
        self._continue_conversation = False
        self._played_event: asyncio.Event | None = None
        self._tts_task: asyncio.Task[None] | None = None

    async def async_added_to_hass(self) -> None:
        """Start the native pipeline after entity registration."""
        await super().async_added_to_hass()
        await self.async_start()

    async def async_will_remove_from_hass(self) -> None:
        """Stop the pipeline before entity removal."""
        await self.async_stop()
        await super().async_will_remove_from_hass()

    @callback
    def async_get_configuration(self) -> AssistSatelliteConfiguration:
        """Expose the server-side wake word configuration."""
        return AssistSatelliteConfiguration(
            available_wake_words=[
                AssistSatelliteWakeWord("alyx", "Alyx", ["fr"]),
                AssistSatelliteWakeWord("okay_nabu", "Okay Nabu", ["en"]),
            ],
            active_wake_words=["alyx", "okay_nabu"],
            max_active_wake_words=0,
        )

    async def async_set_configuration(
        self, config: AssistSatelliteConfiguration
    ) -> None:
        """Keep configuration server-owned; wake models are not local to Android."""
        if not config.active_wake_words:
            raise ValueError("At least one server-side wake word is required")

    async def async_start(self) -> None:
        """Start the dormant-until-enabled native wake pipeline."""
        if self._pipeline_task is None:
            self._stopped = False
            self._pipeline_task = self.config_entry.async_create_background_task(
                self.hass, self._pipeline_loop(), f"{self.entity_id}_pipeline"
            )

    async def async_stop(self) -> None:
        """Cancel the native pipeline and clear all turn state."""
        self._stopped = True
        self._audio_queue.put_nowait(None)
        if self._pipeline_task is not None:
            self._pipeline_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pipeline_task
            self._pipeline_task = None
        self._turn_id = None
        self._continue_conversation = False
        self._played_event = None
        if self._tts_task is not None:
            self._tts_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tts_task
            self._tts_task = None

    async def _pipeline_loop(self) -> None:
        while not self._stopped:
            turn_id = uuid4().hex
            follow_up = self._continue_conversation
            self._continue_conversation = False
            start_stage = "asr" if follow_up else "wake"
            pipeline_stage = PipelineStage.ASR if follow_up else PipelineStage.WAKE_WORD
            self._turn_id = turn_id
            self._audio_queue = asyncio.Queue()
            self._played_event = asyncio.Event()
            self._hassmic.send_wyoming_event(
                WyomingEvent(
                    turn_id=turn_id,
                    run_pipeline=WyomingEventRunPipeline(
                        start_stage=start_stage,
                        end_stage="tts",
                        restart_on_end=False,
                    ),
                )
            )
            try:
                await self.async_accept_pipeline_from_satellite(
                    self._audio_stream(),
                    start_stage=pipeline_stage,
                    end_stage=PipelineStage.TTS,
                )
                if self._tts_task is not None:
                    await self._tts_task
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("HassMic native Assist pipeline failed")
            finally:
                self._turn_id = None
                self._audio_queue.put_nowait(None)

    async def _audio_stream(self) -> AsyncGenerator[bytes, None]:
        while (chunk := await self._audio_queue.get()) is not None:
            yield chunk

    @callback
    def handle_client_event(self, event: ClientEvent) -> None:
        """Accept only correlated Android events for the active pipeline."""
        which, value = betterproto.which_one_of(event, "event")
        if which != "wyoming_event" or value is None:
            return

        wyoming_which, wyoming_value = betterproto.which_one_of(value, "event")
        if value.turn_id != self._turn_id:
            return

        if wyoming_which == "audio_chunk":
            self._audio_queue.put_nowait(value.payload)
        elif wyoming_which == "audio_stop":
            self._audio_queue.put_nowait(None)
        elif wyoming_which == "played":
            if self._played_event is not None:
                self._played_event.set()
            self.tts_response_finished()
        elif wyoming_which == "error":
            self._audio_queue.put_nowait(None)

    @callback
    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Stream TTS and keep completion tied to Android playback."""
        if event.type.name == "INTENT_END" and event.data:
            intent = event.data.get("intent_output") or {}
            self._continue_conversation = bool(
                intent.get("continue_conversation", False)
            )
        if event.type.name == "TTS_END" and event.data:
            output = event.data.get("tts_output")
            if output and (token := output.get("token")) and self._turn_id:
                stream = tts.async_get_stream(self.hass, token)
                if stream is not None:
                    self._tts_task = self.config_entry.async_create_background_task(
                        self.hass,
                        self._stream_tts(stream, self._turn_id),
                        f"{self.entity_id}_tts",
                    )
        _LOGGER.debug("HassMic native pipeline event: %s", event.type)

    async def _stream_tts(self, stream, turn_id: str) -> None:
        """Send a PCM WAV TTS stream and wait for the Android played event."""
        header = b""
        started = False
        rate = 0
        width = 0
        channels = 0
        try:
            async for chunk in stream.async_stream_result():
                if not started:
                    header += chunk
                    if len(header) < 44:
                        continue
                    rate = int.from_bytes(header[24:28], "little")
                    width = int.from_bytes(header[34:36], "little") // 8
                    channels = int.from_bytes(header[22:24], "little")
                    if rate <= 0 or width <= 0 or channels <= 0:
                        raise ValueError("invalid TTS WAV header")
                    self._hassmic.send_wyoming_event(
                        WyomingEvent(
                            turn_id=turn_id,
                            audio_start=WyomingEventAudioStart(
                                rate=rate, width=width, channels=channels
                            ),
                        )
                    )
                    started = True
                    chunk = header[44:]

                for offset in range(0, len(chunk), 8192):
                    data = chunk[offset : offset + 8192]
                    self._hassmic.send_wyoming_event(
                        WyomingEvent(
                            turn_id=turn_id,
                            payload=data,
                            audio_chunk=WyomingEventAudioChunk(
                                rate=rate, width=width, channels=channels
                            ),
                        )
                    )

            if started:
                self._hassmic.send_wyoming_event(
                    WyomingEvent(
                        turn_id=turn_id,
                        audio_stop=WyomingEventAudioStop(),
                    )
                )
                if self._played_event is not None:
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self._played_event.wait(), 8.0)
        except Exception:
            _LOGGER.exception("Unable to stream HassMic TTS")
            self._audio_queue.put_nowait(None)
