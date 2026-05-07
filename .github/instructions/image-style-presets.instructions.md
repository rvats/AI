---
description: "Use when creating or editing brand visuals, thumbnails, hero banners, product cutouts, or background replacements. Defines brand-consistent defaults for color, lighting, typography, composition, and exports."
name: "Image Style Presets"
---
# Image Style Presets

Use these defaults unless the user provides a stronger brand system in the prompt, attached assets, or repository context.

## Brand Discovery Order
- First reuse brand colors, logos, typography, and layout cues found in the workspace.
- If the workspace does not define a visual system, use the fallback defaults below and keep them consistent across all variants.
- If style direction is still ambiguous, ask before generating final assets.

## Fallback Brand Defaults
- Palette: deep navy `#102A43`, warm sand `#F0E6D2`, signal coral `#E76F51`, muted teal `#2A9D8F`, clean white `#FAFAF7`.
- Contrast: keep foreground-to-background contrast high enough for readable overlay text.
- Saturation: prefer controlled, slightly cinematic color grading over neon-heavy palettes.

## Lighting Defaults
- Use soft directional light with one clear key light.
- Preserve natural shadow edges; avoid harsh flash unless the prompt explicitly calls for it.
- For product cutouts, use even studio lighting and a subtle grounding shadow.
- For hero imagery, favor atmospheric depth, warm highlights, and restrained bloom.

## Typography Defaults
- Primary headline style: bold geometric sans.
- Secondary or editorial accent: elegant serif only when the design benefits from contrast.
- Keep typography to at most two families in one composition.
- Prefer short, high-contrast headline blocks over dense paragraphs.
- Avoid novelty fonts, compressed all-caps everywhere, and weak contrast over busy imagery.

## Composition Defaults
- Thumbnail: one dominant subject, aggressive focal hierarchy, legible text at small size.
- Hero: wide composition, clear safe area for copy, restrained background clutter.
- Product cutout: centered or grid-aligned subject, clean edge separation, realistic shadow.
- Background replacement: match perspective, color temperature, and shadow direction to the subject.

## Output Rules
- Never overwrite the original source image.
- Save derived assets with a task suffix such as `-thumb`, `-hero`, `-cutout`, `-bg`, `-edit`, or `-retouched`.
- Prefer lowercase kebab-case output names.
- Keep exports in a derived or output location, not inside raw or source asset folders.
