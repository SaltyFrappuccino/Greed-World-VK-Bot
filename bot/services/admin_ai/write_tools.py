from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import cards as cards_crud
from bot.database.crud import character_arts as arts_crud
from bot.database.crud import characters as characters_crud
from bot.database.crud import contours as contours_crud
from bot.database.crud import trophies as trophies_crud
from bot.services import (
    card_service,
    character_art_service,
    character_service,
    contour_service,
    book_slot_service,
    shakei_service,
    trophy_service,
    vk_discussion_service,
)
from bot.services.admin_ai.values import (
    CARD_UPDATE_FIELDS,
    CHARACTER_CREATE_FIELDS,
    CHARACTER_UPDATE_FIELDS,
    _card,
    _card_data,
    _card_type,
    _character,
    _character_data,
    _dict,
    _integer,
    _normalize_card_fields,
    _normalize_character_create_fields,
    _optional_int,
    _rarity,
    _reject_unknown_fields,
    _text,
    is_action_reference,
)
from bot.services.errors import NotFoundError, ValidationError

async def _action_snapshot(
    session: AsyncSession, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    result: dict[str, object] = {}
    if name in {"character_import_discussion", "character_link_discussion"}:
        application = await vk_discussion_service.get_application(
            _integer(arguments, "comment_id")
        )
        existing = await characters_crud.get_by_discussion_source(
            session,
            group_id=application.group_id,
            topic_id=application.topic_id,
            comment_id=application.comment_id,
        )
        target_character_id = (
            _integer(arguments, "character_id")
            if name == "character_link_discussion"
            else None
        )
        if existing is not None and existing.id != target_character_id:
            raise ValidationError(
                f"Комментарий #{application.comment_id} уже импортирован как "
                f"анкета #{existing.id} · {existing.name}."
            )
        result[f"discussion:{application.comment_id}"] = {
            "group_id": application.group_id,
            "topic_id": application.topic_id,
            "comment_id": application.comment_id,
            "author_vk_id": application.author_vk_id,
            "author_name": application.author_name,
            "content_hash": application.content_hash,
            "photo_count": len(application.photos),
        }
    if "character_id" in arguments:
        character = await _character(session, _integer(arguments, "character_id"))
        result[f"character:{character.id}"] = _character_data(character)
        if name == "character_delete":
            ownerships = await cards_crud.list_character_ownerships(session, character.id)
            contours = await contours_crud.list_for_character(session, character.id)
            arts = await arts_crud.list_for_character(session, character.id)
            result[f"character_contents:{character.id}"] = {
                "ownership_ids": [item.id for item in ownerships],
                "contour_ids": [item.id for item in contours],
                "art_ids": [item.id for item in arts],
            }
        if name == "ordinary_card_revoke" and arguments.get("name"):
            expected_name = str(arguments["name"]).strip().casefold()
            ownerships = await cards_crud.list_character_ownerships(
                session, character.id
            )
            result[f"ordinary_stack:{character.id}:{expected_name}"] = [
                {
                    "id": item.id,
                    "bound_contour_id": (
                        item.contour_component.contour_id
                        if item.contour_component is not None
                        else None
                    ),
                }
                for item in ownerships
                if item.card_id is None
                and item.display_name.casefold() == expected_name
            ]
    if "card_id" in arguments and not is_action_reference(arguments["card_id"]):
        card = await _card(session, _integer(arguments, "card_id"))
        ownerships = await cards_crud.list_card_ownerships(session, card.id)
        result[f"card:{card.id}"] = _card_data(card) | {
            "live_copies": len(ownerships),
            "ownerships": [
                {
                    "id": item.id,
                    "character_id": item.character_id,
                    "bound_contour_id": (
                        item.contour_component.contour_id
                        if item.contour_component is not None
                        else None
                    ),
                }
                for item in ownerships
            ],
        }
    if "contour_id" in arguments and not is_action_reference(arguments["contour_id"]):
        contour = await contours_crud.get_by_id(session, _integer(arguments, "contour_id"))
        if contour is None:
            raise NotFoundError("Контур не найден.")
        result[f"contour:{contour.id}"] = {
            "id": contour.id,
            "character_id": contour.character_id,
            "slot": contour.slot,
            "capacity": contour.card_capacity,
            "name": contour.name,
            "components": [item.card_ownership_id for item in contour.components],
            **{field: getattr(contour, field) for field in contour_service.EDITABLE_FIELDS},
        }
    if "ownership_id" in arguments and not is_action_reference(arguments["ownership_id"]):
        ownership_id = _integer(arguments, "ownership_id")
        ownership = await cards_crud.get_ownership_by_id(session, ownership_id)
        if ownership is None:
            raise NotFoundError(f"Копия карты #{ownership_id} не найдена.")
        result[f"ownership:{ownership_id}"] = {
            "id": ownership.id,
            "character_id": ownership.character_id,
            "card_id": ownership.card_id,
            "name": ownership.display_name,
            "bound_contour_id": (
                ownership.contour_component.contour_id
                if ownership.contour_component is not None
                else None
            ),
        }
    if "component_id" in arguments and not is_action_reference(arguments["component_id"]):
        component_id = _integer(arguments, "component_id")
        component = await contours_crud.get_component(session, component_id)
        if component is None:
            raise NotFoundError(f"Компонент Контура #{component_id} не найден.")
        result[f"component:{component_id}"] = {
            "id": component.id,
            "contour_id": component.contour_id,
            "ownership_id": component.card_ownership_id,
            "position": component.position,
        }
    if "art_id" in arguments and not is_action_reference(arguments["art_id"]):
        art_id = _integer(arguments, "art_id")
        art = await arts_crud.get_by_id(session, art_id)
        if art is None:
            raise NotFoundError(f"Арт #{art_id} не найден.")
        result[f"art:{art_id}"] = {
            "id": art.id,
            "character_id": art.character_id,
            "caption": art.caption,
            "is_primary": art.is_primary,
            "sha256": art.sha256,
            "storage_key": art.storage_key,
        }
    if "trophy_id" in arguments and not is_action_reference(arguments["trophy_id"]):
        trophy_id = _integer(arguments, "trophy_id")
        trophy = await trophies_crud.get_by_id(session, trophy_id)
        if trophy is None:
            raise NotFoundError(f"Трофей #{trophy_id} не найден.")
        result[f"trophy:{trophy_id}"] = {
            "id": trophy.id,
            "character_id": trophy.character_id,
            "name": trophy.name,
            "rank": trophy.rank.value,
            "description": trophy.description,
            "reward": trophy.reward,
        }
    for raw_ownership_id in arguments.get("ownership_ids", []):
        if isinstance(raw_ownership_id, str) and is_action_reference(raw_ownership_id):
            continue
        ownership_id = int(raw_ownership_id)
        ownership = await cards_crud.get_ownership_by_id(session, ownership_id)
        if ownership is None:
            raise NotFoundError(f"Копия карты #{ownership_id} не найдена.")
        result[f"ownership:{ownership_id}"] = {
            "id": ownership.id,
            "character_id": ownership.character_id,
            "card_id": ownership.card_id,
            "name": ownership.display_name,
            "bound_contour_id": (
                ownership.contour_component.contour_id
                if ownership.contour_component is not None
                else None
            ),
        }
    return result


async def _execute_action(
    session: AsyncSession,
    name: str,
    arguments: dict[str, object],
    *,
    admin_vk_id: int,
    plan_id: int,
) -> str:
    if name == "character_link_discussion":
        application = await vk_discussion_service.get_application(
            _integer(arguments, "comment_id")
        )
        item = await _character(session, _integer(arguments, "character_id"))
        existing = await characters_crud.get_by_discussion_source(
            session,
            group_id=application.group_id,
            topic_id=application.topic_id,
            comment_id=application.comment_id,
        )
        if existing is not None and existing.id != item.id:
            raise ValidationError(
                f"Комментарий уже связан с анкетой #{existing.id}."
            )
        await characters_crud.update(
            session,
            item,
            source_group_id=application.group_id,
            source_topic_id=application.topic_id,
            source_comment_id=application.comment_id,
            source_comment_hash=application.content_hash,
        )
        return (
            f"Анкета #{item.id} · {item.name} связана с комментарием "
            f"#{application.comment_id}."
        )
    if name == "character_import_discussion":
        application = await vk_discussion_service.get_application(
            _integer(arguments, "comment_id")
        )
        existing = await characters_crud.get_by_discussion_source(
            session,
            group_id=application.group_id,
            topic_id=application.topic_id,
            comment_id=application.comment_id,
        )
        if existing is not None:
            raise ValidationError(
                f"Комментарий уже импортирован как анкета #{existing.id}."
            )
        fields = _normalize_character_create_fields(
            _dict(arguments, "fields", optional=True)
        )
        owner_vk_id = int(arguments.get("owner_vk_id") or application.author_vk_id)
        item = await character_service.create_character(
            session,
            vk_id=owner_vk_id,
            name=_text(arguments, "name"),
            source_group_id=application.group_id,
            source_topic_id=application.topic_id,
            source_comment_id=application.comment_id,
            source_comment_hash=application.content_hash,
            **fields,
        )
        art_ids: list[int] = []
        if bool(arguments.get("include_photos", True)):
            for index, photo in enumerate(application.photos):
                art = await character_art_service.add_from_vk(
                    session,
                    character_id=item.id,
                    source_url=photo.url,
                    vk_attachment=photo.attachment,
                    caption=f"Арт из обсуждения · {item.name}",
                    admin_vk_id=admin_vk_id,
                    make_primary=index == 0,
                )
                art_ids.append(art.id)
        suffix = (
            " Прикреплены арты: " + ", ".join(f"#{art_id}" for art_id in art_ids) + "."
            if art_ids
            else ""
        )
        return (
            f"Импортирована анкета #{item.id} · {item.name} из комментария "
            f"#{application.comment_id}; владелец https://vk.ru/id{owner_vk_id}."
            f"{suffix}"
        )
    if name == "character_create":
        fields = _normalize_character_create_fields(_dict(arguments, "fields", optional=True))
        item = await character_service.create_character(session, vk_id=_integer(arguments, "vk_id"), name=_text(arguments, "name"), **fields)
        art_ids: list[int] = []
        for art_data in arguments.get("arts", []):
            art = await character_art_service.add_from_vk(
                session,
                character_id=item.id,
                source_url=_text(art_data, "source_url"),
                vk_attachment=None,
                caption=str(art_data.get("caption", "")),
                admin_vk_id=admin_vk_id,
                make_primary=bool(art_data.get("make_primary", False)),
            )
            art_ids.append(art.id)
        suffix = (
            " Прикреплены арты: " + ", ".join(f"#{art_id}" for art_id in art_ids) + "."
            if art_ids else ""
        )
        return f"Создана анкета #{item.id} · {item.name}.{suffix}"
    if name == "character_update":
        item = await _character(session, _integer(arguments, "character_id"))
        fields = _dict(arguments, "fields")
        _reject_unknown_fields(fields, CHARACTER_UPDATE_FIELDS, "анкеты")
        if "name" in fields:
            await character_service.rename_character(session, item, str(fields.pop("name")))
        if "vk_id" in fields:
            await character_service.change_owner(session, item, int(fields.pop("vk_id")))
        if fields:
            await character_service.update_profile(session, item, **fields)
        return f"Обновлена анкета #{item.id} · {item.name}."
    if name == "character_delete":
        item_id = _integer(arguments, "character_id")
        return f"Удалена анкета #{item_id} · {await character_service.delete_character(session, item_id)}."
    if name == "character_approve":
        item = await character_service.approve(session, _integer(arguments, "character_id"))
        return f"Подтверждена анкета #{item.id} · {item.name}."
    if name == "character_set_stat":
        item = await character_service.set_stat(session, _integer(arguments, "character_id"), _text(arguments, "stat"), _integer(arguments, "value"))
        return f"Изменён стат анкеты #{item.id}."
    if name == "character_set_rating":
        item = await character_service.set_rating(session, _integer(arguments, "character_id"), _rarity(arguments["rating"]))
        return f"Рейтинг анкеты #{item.id}: {item.overall_rating.value}."
    if name == "character_change_owner":
        item = await _character(session, _integer(arguments, "character_id"))
        await character_service.change_owner(session, item, _integer(arguments, "vk_id"))
        return f"Владелец анкеты #{item.id} изменён."
    if name == "card_create":
        item = await card_service.create_card(
            session,
            name=_text(arguments, "name"), card_type=_card_type(arguments["card_type"]),
            kind=_text(arguments, "kind"), rarity=_rarity(arguments["rarity"]), admin_vk_id=admin_vk_id,
            number=_optional_int(arguments.get("number")), description=str(arguments.get("description", "")),
            usage=str(arguments.get("usage", "")), transform_limit=_optional_int(arguments.get("transform_limit")),
        )
        return {
            "message": f"Создана карта #{item.id} · {item.name}.",
            "card_id": item.id,
        }
    if name == "card_create_and_grant":
        character_id = _integer(arguments, "character_id")
        quantity = int(arguments.get("quantity", 1))
        item = await card_service.create_card(
            session,
            name=_text(arguments, "name"), card_type=_card_type(arguments["card_type"]),
            kind=_text(arguments, "kind"), rarity=_rarity(arguments["rarity"]), admin_vk_id=admin_vk_id,
            number=_optional_int(arguments.get("number")), description=str(arguments.get("description", "")),
            usage=str(arguments.get("usage", "")), transform_limit=_optional_int(arguments.get("transform_limit")),
        )
        ownerships = await card_service.grant_card_copies(
            session, item.id, character_id, quantity=quantity
        )
        ownership_ids = [int(getattr(item, "id")) for item in ownerships]
        return {
            "message": (
                f"Создана карта #{item.id} · {item.name} и выдана персонажу "
                f"#{character_id} в количестве {quantity}; {_ownership_ids_text(ownerships)}."
            ),
            "card_id": item.id,
            "character_id": character_id,
            "ownership_ids": ownership_ids,
        }
    if name == "card_update":
        fields = _dict(arguments, "fields")
        _reject_unknown_fields(fields, CARD_UPDATE_FIELDS, "карты")
        item = await card_service.update_card(session, _integer(arguments, "card_id"), **_normalize_card_fields(fields))
        return f"Обновлена карта #{item.id} · {item.name}."
    if name == "card_delete":
        item_id = _integer(arguments, "card_id")
        return f"Удалена карта #{item_id} · {await card_service.delete_card(session, item_id)}."
    if name == "card_grant":
        quantity = int(arguments.get("quantity", 1))
        items = await card_service.grant_card_copies(
            session,
            _integer(arguments, "card_id"),
            _integer(arguments, "character_id"),
            quantity=quantity,
        )
        ownership_ids = [int(getattr(item, "id")) for item in items]
        return {
            "message": f"Выдано карт: {quantity}; {_ownership_ids_text(items)}.",
            "card_id": _integer(arguments, "card_id"),
            "character_id": _integer(arguments, "character_id"),
            "ownership_ids": ownership_ids,
        }
    if name == "card_revoke":
        quantity = int(arguments.get("quantity", 1))
        await card_service.revoke_card_copies(
            session,
            _integer(arguments, "card_id"),
            _integer(arguments, "character_id"),
            quantity=quantity,
        )
        return f"Забрано свободных копий карты: {quantity}."
    if name == "ordinary_card_grant":
        quantity = int(arguments.get("quantity", 1))
        items = await card_service.grant_ordinary_cards(
            session, character_id=_integer(arguments, "character_id"), name=_text(arguments, "name"),
            kind=_text(arguments, "kind"), rarity=_rarity(arguments["rarity"]),
            description=str(arguments.get("description", "")), usage=str(arguments.get("usage", "")),
            quantity=quantity,
        )
        ownership_ids = [int(getattr(item, "id")) for item in items]
        return {
            "message": f"Добавлено Обычных карт: {quantity}; {_ownership_ids_text(items)}.",
            "character_id": _integer(arguments, "character_id"),
            "ownership_ids": ownership_ids,
        }
    if name == "ordinary_card_revoke":
        character_id = _integer(arguments, "character_id")
        if arguments.get("ownership_id") not in (None, ""):
            ownership = await cards_crud.get_ownership_by_id(
                session, _integer(arguments, "ownership_id")
            )
            if (
                ownership is None
                or ownership.card_id is not None
                or ownership.character_id != character_id
            ):
                raise NotFoundError("Обычная карта не найдена у выбранного персонажа.")
            card_name = ownership.display_name
            quantity = 1
        else:
            card_name = _text(arguments, "name")
            quantity = int(arguments.get("quantity", 1))
        await card_service.revoke_ordinary_cards(
            session,
            character_id=character_id,
            name=card_name,
            quantity=quantity,
        )
        return f"Обычная карта «{card_name}» забрана в количестве {quantity}."
    if name == "contour_create":
        item = await contour_service.create_contour(
            session, character_id=_integer(arguments, "character_id"), ownership_ids=[int(value) for value in arguments.get("ownership_ids", [])],
            name=_text(arguments, "name"), admin_vk_id=admin_vk_id, slot=_optional_int(arguments.get("slot")),
            card_capacity=int(arguments.get("card_capacity", 2)), **_dict(arguments, "fields", optional=True),
        )
        return f"Создан Контур #{item.id} · {item.name}."
    if name == "contour_update":
        item = await contour_service.update_contour(session, contour_id=_integer(arguments, "contour_id"), admin_vk_id=admin_vk_id, **_dict(arguments, "fields"))
        return f"Обновлён Контур #{item.id} · {item.name}."
    if name == "contour_disassemble":
        item_id = _integer(arguments, "contour_id")
        _, title = await contour_service.disassemble(session, contour_id=item_id, admin_vk_id=admin_vk_id)
        return f"Разобран Контур #{item_id} · {title}."
    if name == "contour_limit_set":
        item = await contour_service.set_character_limit(session, character_id=_integer(arguments, "character_id"), value=_integer(arguments, "value"), admin_vk_id=admin_vk_id)
        return f"Лимит Контуров анкеты #{item.id}: {item.contour_limit}."
    if name == "contour_capacity_set":
        item = await contour_service.set_capacity(session, contour_id=_integer(arguments, "contour_id"), value=_integer(arguments, "value"), admin_vk_id=admin_vk_id)
        return f"Размер Контура #{item.id}: {item.card_capacity}."
    if name == "free_slot_limit_set":
        item = await book_slot_service.set_free_slot_limit(
            session,
            character_id=_integer(arguments, "character_id"),
            value=_integer(arguments, "value"),
            admin_vk_id=admin_vk_id,
        )
        return f"Свободных слотов анкеты #{item.id}: {item.free_slot_limit}."
    if name == "trophy_award":
        item = await trophy_service.award(
            session,
            character_id=_integer(arguments, "character_id"),
            name=_text(arguments, "name"),
            rank=_text(arguments, "rank"),
            description=str(arguments.get("description", "")),
            reward=str(arguments.get("reward", "")),
            admin_vk_id=admin_vk_id,
        )
        return f"Выдан трофей #{item.id} · {item.name} анкете #{item.character_id}."
    if name == "trophy_update":
        item = await trophy_service.update(
            session,
            trophy_id=_integer(arguments, "trophy_id"),
            admin_vk_id=admin_vk_id,
            **_dict(arguments, "fields"),
        )
        return f"Обновлён трофей #{item.id} · {item.name}."
    if name == "trophy_delete":
        item = await trophy_service.remove(
            session,
            trophy_id=_integer(arguments, "trophy_id"),
            admin_vk_id=admin_vk_id,
        )
        return f"Удалён трофей #{item.id} · {item.name}."
    if name == "contour_card_add":
        item = await contour_service.add_card(session, contour_id=_integer(arguments, "contour_id"), ownership_id=_integer(arguments, "ownership_id"), admin_vk_id=admin_vk_id)
        return f"Карта добавлена в Контур #{item.id}."
    if name == "contour_card_remove":
        item = await contour_service.remove_card(session, component_id=_integer(arguments, "component_id"), admin_vk_id=admin_vk_id)
        return f"Карта убрана из Контура #{item.id}."
    if name == "contour_card_replace":
        item = await contour_service.replace_card(session, component_id=_integer(arguments, "component_id"), ownership_id=_integer(arguments, "ownership_id"), admin_vk_id=admin_vk_id)
        return f"Карта заменена в Контуре #{item.id}."
    if name == "shakei_change":
        character_id, delta = _integer(arguments, "character_id"), int(arguments.get("delta", 0))
        if delta == 0:
            raise ValidationError("Изменение Шакеев не может быть нулевым.")
        if delta > 0:
            await shakei_service.grant(session, character_id=character_id, amount=delta, admin_vk_id=admin_vk_id, reason=f"AI-план #{plan_id}")
        else:
            await shakei_service.deduct(session, character_id=character_id, amount=abs(delta), admin_vk_id=admin_vk_id, reason=f"AI-план #{plan_id}")
        item = await _character(session, character_id)
        return f"Шакеи анкеты #{item.id}: {delta:+d}; баланс {item.shakei_balance}."
    if name == "character_art_add":
        art = await character_art_service.add_from_vk(
            session,
            character_id=_integer(arguments, "character_id"),
            source_url=_text(arguments, "source_url"),
            vk_attachment=None,
            caption=str(arguments.get("caption", "")),
            admin_vk_id=admin_vk_id,
            make_primary=bool(arguments.get("make_primary", False)),
        )
        return f"Добавлен арт #{art.id} к анкете #{art.character_id}."
    if name == "character_art_set_primary":
        art = await character_art_service.set_primary(
            session,
            art_id=_integer(arguments, "art_id"),
            admin_vk_id=admin_vk_id,
        )
        return f"Арт #{art.id} назначен основным."
    if name == "character_art_update_caption":
        art = await character_art_service.update_caption(
            session,
            art_id=_integer(arguments, "art_id"),
            caption=str(arguments.get("caption", "")),
            admin_vk_id=admin_vk_id,
        )
        return f"Подпись арта #{art.id} обновлена."
    if name == "character_art_delete":
        art_id = _integer(arguments, "art_id")
        await character_art_service.delete_art(
            session, art_id=art_id, admin_vk_id=admin_vk_id
        )
        return f"Арт #{art_id} удалён."
    raise ValidationError(f"Неизвестный изменяющий инструмент: {name}.")


def _ownership_ids_text(items: list[object]) -> str:
    ids = [int(getattr(item, "id")) for item in items]
    shown = ", ".join(f"#{value}" for value in ids[:20])
    suffix = f" и ещё {len(ids) - 20}" if len(ids) > 20 else ""
    return f"ID копий: {shown}{suffix}"
