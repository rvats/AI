---
description: "Run a reusable image workflow for thumbnails, hero banners, product cutouts, or background replacements using the Image Studio agent and the shared style presets."
name: "Image Task Kit"
argument-hint: "Task type, source asset path, style direction, dimensions, and output format"
agent: "Image Studio"
---
Use [image style presets](../instructions/image-style-presets.instructions.md) as the default visual system unless the request or attached assets define a stronger brand language.

Complete one of these image tasks:
- Thumbnail
- Hero banner
- Product cutout
- Background replacement

Inputs to collect or confirm:
- Task type
- Source asset path or files
- Audience or channel
- Style direction or reference
- Target dimensions
- Output format

Execution rules:
- Ask for style choices first if the visual direction is vague.
- Do not overwrite source files.
- Name outputs in lowercase kebab-case with a task suffix such as `-thumb`, `-hero`, `-cutout`, `-bg`, `-edit`, or `-retouched`.
- Return exact output file paths and the reproduction steps or commands.

Task-specific defaults:
- Thumbnail: optimize for small-screen readability and immediate focal contrast.
- Hero banner: leave copy-safe space and preserve wide-format balance.
- Product cutout: preserve clean edges and add a subtle grounding shadow if appropriate.
- Background replacement: match perspective, lighting direction, and color temperature to the subject.
