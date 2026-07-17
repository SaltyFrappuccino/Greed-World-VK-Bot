from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import PeerRule

from bot.database.engine import get_session
from bot.keyboards.admin_menu import ai_collect_menu, ai_confirm_menu, back_to_admin
from bot.keyboards.main_menu import cancel
from bot.middlewares.auth import AdminRule
from bot.services import ai_service, character_service, contour_service
from bot.services.errors import ServiceError, ValidationError
from bot.services.vk_service import resolve_user_id
from bot.states import AdminAIState, clear_state, state_dispenser
from bot.utils.messages import answer_long

labeler = BotLabeler(auto_rules=[PeerRule(from_chat=False), AdminRule()])
labeler.vbml_ignore_case = True


@labeler.message(payload={"cmd": "admin_ai_character"})
async def start_character(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminAIState.CHARACTER_OWNER)
    await message.answer(
        "Кому будет принадлежать анкета? Пришлите VK ID, упоминание или ссылку "
        "на профиль.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminAIState.CHARACTER_OWNER)
async def pick_character_owner(message: Message, **_: object) -> None:
    try:
        owner_vk_id = await resolve_user_id(message.ctx_api, message.text)
    except ServiceError as error:
        await message.answer(str(error), keyboard=cancel())
        return

    await state_dispenser.set(
        message.peer_id,
        AdminAIState.CHARACTER_SOURCE,
        owner_vk_id=owner_vk_id,
        source_parts=[],
        image_urls=[],
    )
    await message.answer(
        "Присылайте исходную анкету любым количеством сообщений. К тексту можно "
        "прикрепить изображения внешности или книги. Я буду только накапливать "
        "материал — когда закончите, нажмите «Готово — обработать».\n\n"
        "Текст и изображения будут переданы в AI Tunnel и Google Gemini.",
        keyboard=ai_collect_menu("admin_ai_character"),
    )


@labeler.message(payload={"cmd": "admin_ai_character_generate"})
async def generate_character(message: Message, **_: object) -> None:
    try:
        state = await _require_state(message, AdminAIState.CHARACTER_SOURCE)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin())
        return

    source_parts = state.payload.get("source_parts", [])
    image_urls = state.payload.get("image_urls", [])
    if not source_parts and not image_urls:
        await message.answer(
            "Сначала пришлите хотя бы один фрагмент текста или изображение.",
            keyboard=ai_collect_menu("admin_ai_character"),
        )
        return

    await message.answer("Обрабатываю анкету…", keyboard=cancel())
    try:
        draft = await ai_service.generate_character(
            "\n\n".join(source_parts), image_urls=image_urls
        )
    except ServiceError as error:
        await message.answer(
            str(error), keyboard=ai_collect_menu("admin_ai_character")
        )
        return

    await state_dispenser.set(
        message.peer_id,
        AdminAIState.CHARACTER_CONFIRM,
        owner_vk_id=state.payload["owner_vk_id"],
        draft=draft.model_dump(),
    )
    await answer_long(
        message,
        ai_service.character_preview(draft),
        keyboard=ai_confirm_menu("admin_ai_character"),
    )


@labeler.message(state=AdminAIState.CHARACTER_SOURCE)
async def collect_character_source(message: Message, **_: object) -> None:
    await _collect_source(
        message,
        AdminAIState.CHARACTER_SOURCE,
        "admin_ai_character",
    )


@labeler.message(payload={"cmd": "admin_ai_character_confirm"})
async def save_character(message: Message, **_: object) -> None:
    try:
        state = await _require_state(message, AdminAIState.CHARACTER_CONFIRM)
        draft = ai_service.CharacterDraft.model_validate(state.payload["draft"])
        fields = ai_service.character_fields(draft)
        name = str(fields.pop("name"))
        async with get_session() as session:
            character = await character_service.create_character(
                session,
                vk_id=state.payload["owner_vk_id"],
                name=name,
                **fields,
            )
    except (ServiceError, ValueError) as error:
        await message.answer(str(error), keyboard=cancel())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Анкета «{character.name}» сохранена.", keyboard=back_to_admin()
    )


@labeler.message(payload={"cmd": "admin_ai_contour"})
async def start_contour(message: Message, **_: object) -> None:
    await state_dispenser.set(message.peer_id, AdminAIState.CONTOUR_CHARACTER)
    await message.answer(
        "Для какого персонажа создаём Контур? Пришлите точное имя.",
        keyboard=cancel(),
    )


@labeler.message(state=AdminAIState.CONTOUR_CHARACTER)
async def pick_contour_character(message: Message, **_: object) -> None:
    async with get_session() as session:
        try:
            character = await character_service.find_character(session, message.text)
        except ServiceError as error:
            await message.answer(str(error), keyboard=cancel())
            return

    await state_dispenser.set(
        message.peer_id,
        AdminAIState.CONTOUR_SOURCE,
        character_id=character.id,
        character_name=character.name,
        character_context=_character_context(character),
        source_parts=[],
        image_urls=[],
    )
    await message.answer(
        f"Персонаж: {character.name}. Присылайте идею или черновик Контура "
        "несколькими сообщениями. Можно приложить изображение его внешнего вида. "
        "Когда закончите, нажмите «Готово — обработать».\n\n"
        "Материал будет передан в AI Tunnel и Google Gemini.",
        keyboard=ai_collect_menu("admin_ai_contour"),
    )


@labeler.message(payload={"cmd": "admin_ai_contour_generate"})
async def generate_contour(message: Message, **_: object) -> None:
    try:
        state = await _require_state(message, AdminAIState.CONTOUR_SOURCE)
    except ServiceError as error:
        await message.answer(str(error), keyboard=back_to_admin())
        return

    payload = state.payload
    source_parts = payload.get("source_parts", [])
    image_urls = payload.get("image_urls", [])
    if not source_parts and not image_urls:
        await message.answer(
            "Сначала пришлите хотя бы один фрагмент текста или изображение.",
            keyboard=ai_collect_menu("admin_ai_contour"),
        )
        return

    await message.answer("Прорабатываю Контур…", keyboard=cancel())
    try:
        draft = await ai_service.generate_contour(
            "\n\n".join(source_parts),
            payload["character_context"],
            image_urls=image_urls,
        )
    except ServiceError as error:
        await message.answer(str(error), keyboard=ai_collect_menu("admin_ai_contour"))
        return

    await state_dispenser.set(
        message.peer_id,
        AdminAIState.CONTOUR_CONFIRM,
        character_id=payload["character_id"],
        character_name=payload["character_name"],
        draft=draft.model_dump(),
    )
    await answer_long(
        message,
        ai_service.contour_preview(draft),
        keyboard=ai_confirm_menu("admin_ai_contour"),
    )


@labeler.message(state=AdminAIState.CONTOUR_SOURCE)
async def collect_contour_source(message: Message, **_: object) -> None:
    await _collect_source(
        message,
        AdminAIState.CONTOUR_SOURCE,
        "admin_ai_contour",
    )


@labeler.message(payload={"cmd": "admin_ai_contour_confirm"})
async def save_contour(message: Message, **_: object) -> None:
    try:
        state = await _require_state(message, AdminAIState.CONTOUR_CONFIRM)
        draft = ai_service.ContourDraft.model_validate(state.payload["draft"])
        fields = ai_service.contour_fields(draft)
        name = str(fields.pop("name"))
        async with get_session() as session:
            contour = await contour_service.create_contour(
                session,
                character_id=state.payload["character_id"],
                name=name,
                admin_vk_id=message.from_id,
                **fields,
            )
    except (ServiceError, ValueError) as error:
        await message.answer(str(error), keyboard=cancel())
        return

    await clear_state(message.peer_id)
    await message.answer(
        f"Контур «{contour.name}» сохранён в слот {contour.slot} персонажа "
        f"{state.payload['character_name']}.",
        keyboard=back_to_admin(),
    )


async def _require_state(message: Message, expected_state: str):
    state = await state_dispenser.get(message.peer_id)
    if state is None or not state.state == expected_state:
        raise ValidationError("Черновик устарел. Запустите AI-сценарий заново.")
    return state


async def _collect_source(message: Message, state_name, action: str) -> None:
    state = message.state_peer
    source_parts = list(state.payload.get("source_parts", []))
    image_urls = list(state.payload.get("image_urls", []))

    text = message.text.strip()
    new_image_urls = _photo_urls(message)
    if not text and not new_image_urls:
        await message.answer(
            "В этом сообщении нет текста или изображения.",
            keyboard=ai_collect_menu(action),
        )
        return

    if text:
        source_parts.append(text)
    image_urls.extend(url for url in new_image_urls if url not in image_urls)
    await state_dispenser.set(
        message.peer_id,
        state_name,
        **{
            **state.payload,
            "source_parts": source_parts,
            "image_urls": image_urls,
        },
    )
    await message.answer(
        f"Добавлено: фрагментов текста — {len(source_parts)}, "
        f"изображений — {len(image_urls)}. Присылайте продолжение или нажмите "
        "«Готово — обработать».",
        keyboard=ai_collect_menu(action),
    )


def _photo_urls(message: Message) -> list[str]:
    urls: list[str] = []
    for photo in message.get_photo_attachments() or []:
        sizes = [size for size in (photo.sizes or []) if size.url]
        original = getattr(photo, "orig_photo", None)
        if original is not None and original.url:
            sizes.append(original)
        if sizes:
            largest = max(sizes, key=lambda size: size.width * size.height)
            urls.append(largest.url)
        elif photo.photo_256:
            urls.append(photo.photo_256)
    return urls


def _character_context(character) -> str:
    return "\n".join(
        part
        for part in (
            f"Имя: {character.name}",
            f"Характер: {character.personality}",
            f"Биография: {character.biography}",
            f"Навыки: {character.skills}",
            f"Дополнительно: {character.additional}",
        )
        if not part.endswith(": ")
    )
