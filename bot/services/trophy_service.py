from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import characters as characters_crud
from bot.database.crud import trophies as trophies_crud
from bot.database.models import CharacterTrophy, TrophyRank
from bot.services import auth_service
from bot.services.errors import NotFoundError, ValidationError


RANK_ALIASES = {
    "бронза": TrophyRank.BRONZE,
    "бронзовый": TrophyRank.BRONZE,
    "bronze": TrophyRank.BRONZE,
    "серебро": TrophyRank.SILVER,
    "серебряный": TrophyRank.SILVER,
    "silver": TrophyRank.SILVER,
    "золото": TrophyRank.GOLD,
    "золотой": TrophyRank.GOLD,
    "gold": TrophyRank.GOLD,
}


def parse_rank(value: TrophyRank | str) -> TrophyRank:
    if isinstance(value, TrophyRank):
        return value
    rank = RANK_ALIASES.get(str(value).strip().casefold())
    if rank is None:
        raise ValidationError("Ранг трофея: Бронзовый, Серебряный или Золотой.")
    return rank


async def award(
    session: AsyncSession,
    *,
    character_id: int,
    name: str,
    rank: TrophyRank | str,
    description: str,
    reward: str,
    admin_vk_id: int,
) -> CharacterTrophy:
    auth_service.require_admin(admin_vk_id)
    character = await characters_crud.get_by_id_for_update(session, character_id)
    if character is None:
        raise NotFoundError("Анкета не найдена.")
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError("Название трофея не может быть пустым.")
    return await trophies_crud.create(
        session,
        character_id=character.id,
        name=clean_name,
        rank=parse_rank(rank),
        description=description.strip(),
        reward=reward.strip(),
        awarded_by=admin_vk_id,
    )


async def update(
    session: AsyncSession,
    *,
    trophy_id: int,
    admin_vk_id: int,
    **fields: object,
) -> CharacterTrophy:
    auth_service.require_admin(admin_vk_id)
    trophy = await trophies_crud.get_by_id_for_update(session, trophy_id)
    if trophy is None:
        raise NotFoundError("Трофей не найден.")
    allowed = {"name", "rank", "description", "reward"}
    if unknown := set(fields) - allowed:
        raise ValidationError("Нельзя изменить поля: " + ", ".join(sorted(unknown)))
    if "name" in fields:
        fields["name"] = str(fields["name"]).strip()
        if not fields["name"]:
            raise ValidationError("Название трофея не может быть пустым.")
    if "rank" in fields:
        fields["rank"] = parse_rank(fields["rank"])
    for field in ("description", "reward"):
        if field in fields:
            fields[field] = str(fields[field]).strip()
    for key, value in fields.items():
        setattr(trophy, key, value)
    await session.flush()
    return trophy


async def remove(
    session: AsyncSession, *, trophy_id: int, admin_vk_id: int
) -> CharacterTrophy:
    auth_service.require_admin(admin_vk_id)
    trophy = await trophies_crud.get_by_id_for_update(session, trophy_id)
    if trophy is None:
        raise NotFoundError("Трофей не найден.")
    await trophies_crud.delete(session, trophy)
    return trophy
