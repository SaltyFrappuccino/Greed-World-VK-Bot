from pydantic import BaseModel, ConfigDict, Field

from bot.database.models import Rarity


class CharacterDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Имя персонажа")
    age: int | None = Field(description="Возраст; null, если он принципиально неизвестен")
    gender: str = Field(description="Пол персонажа")
    appearance: str = Field(description="Внешность персонажа и его книги")
    personality: str = Field(description="Характер персонажа")
    biography: str = Field(description="Биография персонажа")
    stress_resistance: int | None = Field(ge=1, le=5)
    speech: int | None = Field(ge=1, le=5)
    intuition: int | None = Field(ge=1, le=5)
    spine: int | None = Field(ge=1, le=5)
    will: int | None = Field(ge=1, le=5)
    scent: int | None = Field(ge=1, le=5)
    skills: list[str] = Field(
        description="Короткие нарративные теги навыков без числовых значений"
    )
    additional: str = Field(description="Связи, привычки, страхи и прочие детали")


class ContourDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    appearance: str
    primary_effect: str
    additional_capabilities: str
    activation_conditions: str
    duration: str
    conductivity: str
    overload_impact: str


class CardDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Короткое название карты")
    kind: str = Field(description="Вид содержимого или точный подтип Контурной карты")
    description: str = Field(description="Что карта создаёт или какой эффект даёт")
    usage: str = Field(description="Как активируется, расходуется и какие имеет ограничения")
    rarity: Rarity = Field(description="Редкость H–SS")


