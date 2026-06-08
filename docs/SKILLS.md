# Skills

Skills are JSON files that bundle every stylistic choice for a video — voice, pacing, visual prompt template, aspect ratio, post-processing chain — into one preset. Pick a Skill, write your script, hit Generate. That's the whole interaction.

## Built-in pack

| Skill | Voice | Pacing | Aspect | Music | Subtitles | Post-processing |
|-------|-------|--------|--------|-------|-----------|-----------------|
| **Documentary**     | bm_george 0.95× | slow   | 16:9 | ambient_score    | off | grade_documentary + film_grain_subtle |
| **Explainer**       | af_sarah 1.05×  | medium | 16:9 | upbeat           | on  | grade_bright |
| **Product Showcase** | am_michael 1.0× | medium | 1:1  | corporate        | off | grade_product |
| **Cinematic Story** | bm_george 0.9×  | slow   | 16:9 | emotional_score  | off | grade_cinematic + film_grain + letterbox |
| **Social Short**    | af_heart 1.1×   | fast   | 9:16 | upbeat_energetic | on  | grade_vibrant |
| **Tutorial**        | af_nicole 1.0×  | medium | 16:9 | tutorial_bg      | on  | grade_tutorial |
| **News Brief**      | am_adam 1.05×   | fast   | 16:9 | news_music       | off | grade_news |

## File format

Each Skill lives in `app/skills/{id}.json`:

```json
{
  "id": "documentary",
  "name": "Documentary",
  "description": "Slow, cinematic, third-person narration",
  "voice": "bm_george",
  "voice_speed": 0.95,
  "scene_pacing": "slow",
  "prompt_template": "{narration_chunk}, cinematic documentary style, natural lighting, wide composition, slow camera movement, photorealistic, 4k",
  "aspect_ratio": "16:9",
  "resolution": "1080p",
  "subtitles": false,
  "music_mood": "ambient_score",
  "post_processing": ["color_grade_documentary", "film_grain_subtle"],
  "icon": "documentary.svg"
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id`             | string | Unique slug, must match filename |
| `name`           | string | Display name in the picker |
| `description`    | string | One-liner shown under the name |
| `voice`          | string | Kokoro voice ID — overrides project's voice setting |
| `voice_speed`    | number | TTS playback rate, 0.5–1.5 typical |
| `scene_pacing`   | enum   | `slow` \| `medium` \| `fast` — informational; affects prompt phrasing |
| `prompt_template` | string | Suffix appended to every scene prompt. `{narration_chunk}` placeholder is replaced |
| `aspect_ratio`   | enum   | `16:9` \| `9:16` \| `1:1` \| `4:5` |
| `resolution`     | enum   | `720p` \| `1080p` \| `4K` (via Upscaling) |
| `subtitles`      | bool   | Auto-enable subtitle generation (user can still override) |
| `music_mood`     | string | MusicGen mood key — see `musicgen_client.py:MOOD_PROMPTS` |
| `post_processing` | string[] | List of effect names, applied in order |
| `icon`           | string | (Reserved) SVG filename in `app/skills/icons/` |

## Creating a custom Skill

1. Copy an existing JSON: `cp app/skills/documentary.json app/skills/my-skill.json`
2. Edit:
   - `id` matches new filename without `.json`
   - `name`, `description` for the picker
   - `voice` + `voice_speed` for narration style
   - `prompt_template` for visual style
   - `post_processing` for color/effects
3. Restart the backend (or call `POST /skills/refresh` — TODO)
4. The new Skill appears in the picker automatically

## Available effects

### Color grading (one per Skill, applied first)

| Name | Look |
|------|------|
| `color_grade_cinematic`   | Teal/orange film aesthetic, lifted shadows, pushed warm highlights |
| `color_grade_documentary` | Natural warm tones, slight desaturation, +contrast |
| `color_grade_bright`      | High contrast, neutral-cool, punchy saturation |
| `color_grade_vibrant`     | Maximum saturation, warm bias, high contrast |
| `color_grade_product`     | Clean, neutral, +brightness for hero shots |
| `color_grade_news`        | Slight desaturation, +contrast, sober look |
| `color_grade_tutorial`    | Subtle neutral grade, minimal processing |

### Stylistic overlays (additive, any combination)

| Name | Effect |
|------|--------|
| `letterbox`         | 2.39:1 cinematic black bars |
| `film_grain`        | Heavy 35mm-style noise |
| `film_grain_subtle` | Light digital noise |

## Music moods

Map to MusicGen text prompts in `app/backend/pipeline/musicgen_client.py`:

| Mood | Generated style |
|------|-----------------|
| `ambient_score`     | calm orchestral, slow, cinematic, no percussion |
| `emotional_score`   | strings + piano, slow build, dramatic film music |
| `upbeat`            | light energetic positive pop instrumental |
| `upbeat_energetic`  | high energy electronic, punchy beat |
| `news_music`        | corporate neutral modern, subtle |
| `tutorial_bg`       | lo-fi, subtle, non-distracting |
| `dramatic`          | dark intense orchestral, tension |

## Voices

Kokoro voices, no extra download needed:

| Voice ID | Demographic | Tone |
|----------|-------------|------|
| `af_heart`   | American Female | Energetic, upbeat |
| `af_bella`   | American Female | Warm, friendly |
| `af_sarah`   | American Female | Conversational, neutral |
| `af_nicole`  | American Female | Professional, clear |
| `am_adam`    | American Male   | Authoritative, news-ready |
| `am_michael` | American Male   | Deep, documentary |
| `bf_emma`    | British Female  | Formal, educational |
| `bm_george`  | British Male    | Narration, dramatic |

## Best practices

**Match Skill to content type** — Documentary makes a 30-second TikTok feel wrong, Social Short makes a 5-minute explainer feel hyperactive.

**Keep the prompt template focused** — long templates dilute the LLM's scene-specific output. 5–10 style hints is enough; more starts feeling repetitive across scenes.

**Test with one scene first** — when iterating on a custom Skill, set `num_scenes: 1` to keep the feedback loop short.

**Voice and music mood pair up** — Slow British male + emotional score creates Documentary's signature feel. Fast American female + upbeat energetic creates Social Short. Mix-and-match cautiously.

**Letterbox eats vertical space** — only useful for 16:9 cinematic Skills. Never combine with 9:16.

## Sharing Skills

Skills are pure JSON, so sharing is just file copying. Future plans:

- **Skill marketplace** — community-submitted Skills indexed in `installer/catalog.json`-style metadata
- **Skill export** — UI button to package a Skill + custom icon + sample output into a single shareable archive
- **Skill versioning** — track which Skill version produced which video for reproducibility

PRs that add high-quality Skills are welcome — include a short script + sample output in the PR.
