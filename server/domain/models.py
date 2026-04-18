from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$")


class IntervalSchedule(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["interval"] = "interval"
    interval_seconds: int = Field(gt=0, alias="intervalSeconds")


class CronWeeklySchedule(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["cron_weekly"] = "cron_weekly"
    time: str = Field(description="HH:MM or HH:MM:SS local")
    weekdays: list[int] = Field(
        default_factory=lambda: list(range(7)),
        description="0=Sunday (same as JS)",
    )

    @field_validator("time")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError(f"time must be HH:MM or HH:MM:SS (got {v!r})")
        return v


Schedule = Annotated[
    Union[IntervalSchedule, CronWeeklySchedule],
    Field(discriminator="type"),
]


class Scene(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str = ""
    description: str = ""
    enabled: bool = True
    template_id: str = Field(alias="templateId")
    template_params: dict[str, Any] = Field(default_factory=dict, alias="templateParams")
    schedule: Schedule
    preview_image_url: str | None = Field(None, alias="previewImageUrl")
    tie_break_priority: int = Field(9, alias="tieBreakPriority")


class AppConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scenes: list[Scene] = Field(default_factory=list)
    frame_tuning: dict[str, Any] = Field(default_factory=dict, alias="frameTuning")
    device_profile: dict[str, Any] = Field(default_factory=dict, alias="deviceProfile")


class WallRun(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    scene_id: str = Field(alias="sceneId")
    scene_name: str = Field("", alias="sceneName")
    template_id: str = Field("", alias="templateId")
    started_at: str = Field(alias="startedAt")
    finished_at: str | None = Field(None, alias="finishedAt")
    duration_ms: int | None = Field(None, alias="durationMs")
    ok: bool
    error_message: str | None = Field(None, alias="errorMessage")
    output_path: str | None = Field(None, alias="outputPath")


class UpcomingItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scene_id: str = Field(alias="sceneId")
    at: str
    name: str = ""


class WallState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current_scene_id: str | None = Field(None, alias="currentSceneId")
    current_scene_name: str | None = Field(None, alias="currentSceneName")
    current_template_id: str | None = Field(None, alias="currentTemplateId")
    current_preview_url: str | None = Field(None, alias="currentPreviewUrl")
    upcoming: list[UpcomingItem] = Field(default_factory=list)
    display_active_scene_id: str | None = Field(None, alias="displayActiveSceneId")
    queued_display_scene_ids: list[str] = Field(
        default_factory=list, alias="queuedDisplaySceneIds"
    )
