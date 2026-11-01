# Spec for the Create page: a translator app

Paste this into the Create chat (or attach this file with the + button) after giving the app the name `translator`.

## What the screenshot shows

`meta-app-2026-10-31_14-12-38.png` is a Streamlit chat app ("Translator Chatbot"). A person types a sentence, picks a **source language**
(default *Auto-detect*) and a **target language** (default *Chinese (Simplified)*), and the app answers with the sentence translated.
The conversation in the picture goes Chinese → German → English → Chinese, changing the target language between turns. The sidebar also has
an LLM adapter and model box and a *Clear conversation* button.

## What to build (a GraphLang workflow app, not a Streamlit page)

Create writes a workflow app, so the chat window, the sidebar and the clear button are out of scope: the model and adapter are chosen
by `--llm` or on the Settings page, and each run is one translation. Build the translation itself.

**Name:** `translator`

**Inputs**
- `text` (TEXT, required): what to translate. It may be one word, a sentence or several paragraphs, in any language and script.
- `source_language` (TEXT, default `Auto-detect`): the language of `text`, or `Auto-detect`.
- `target_language` (TEXT, default `Chinese (Simplified)`): the language to translate into, for example `English`, `German`, `Chinese (Simplified)`.

**Output**
- `translation` (TEXT): the translated text and nothing else.

**Steps:** one GENERATE node, `translate`, with its own prompt file. No loop, no branch, no code.

## Rules for the prompt

- Translate the whole of `text` into `target_language`, keeping its meaning, tone and register (formal stays formal).
- If `source_language` is `Auto-detect`, work out the language from the text; otherwise trust the given language.
- Keep the layout: paragraphs, line breaks, lists, numbers, URLs, code and `{{...}}`-style placeholders stay as they are.
- Keep proper names as they are unless the target language has an established form of the name.
- If `text` is already in `target_language`, return it unchanged.
- Reply with the translation only: no preamble, no quotation marks around it, no notes, no explanation, no offer to help further.

## What a good result looks like (check these after it is created)

| `text` | `target_language` | `translation` |
|---|---|---|
| 我毕业于中国科学技术大学。 | German | Ich habe meinen Abschluss an der Universität für Wissenschaft und Technologie Chinas gemacht. (wording may differ) |
| I graduated from the University of Science and Technology of China. | Chinese (Simplified) | 我毕业于中国科学技术大学。 |
| (the German sentence above) | English | I graduated from the University of Science and Technology of China. (wording may differ) |

The app should validate (`graf validate`), run with one model call, and the output should hold only the translation.

## Later changes to try in the Create chat

- "Also return the language you detected as `detected_language`."
- "Add an input `style` (formal, casual, literary) that the translation follows."
- "Read the text to translate from an attached document instead of typing it" (this needs `text` to accept a file path as the compliance_audit recipe's `document` does).
