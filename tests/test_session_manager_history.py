from nanobot.session.manager import Session


def test_get_history_sanitizes_multimodal_list_content_to_text() -> None:
    session = Session(
        key='web:sess_test',
        messages=[
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'describe this image'},
                    {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,abc'}},
                ],
            }
        ],
    )

    history = session.get_history()

    assert history[0]['role'] == 'user'
    assert history[0]['content'] == 'describe this image\n[image]'


def test_get_history_handles_list_without_text_or_image() -> None:
    session = Session(
        key='web:sess_test',
        messages=[
            {
                'role': 'user',
                'content': [{'type': 'unknown', 'value': 'ignored'}],
            }
        ],
    )

    history = session.get_history()

    assert history[0]['content'] == ''
