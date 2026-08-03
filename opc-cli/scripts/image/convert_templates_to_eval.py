"""Convert scraped imagejson templates to eval prompt JSON files.

Strategy: imagejson templates have wildly varying content schemas.
We preserve the raw content but use the reliable `description` field
as the primary prompt text. The structured content is flattened and
appended for additional detail."""

import json
import os
import re

INPUT_FILE = os.path.join(os.path.dirname(__file__), 'examples', 'imagejson_templates_raw.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'eval', 'prompts')


def slugify(name):
    s = name.lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '_', s)
    return s[:80]


def flatten_dict(d, prefix=''):
    """Recursively flatten a dict to a list of "key: value" strings."""
    items = []
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key))
            elif isinstance(v, list):
                # For lists of dicts, flatten each item
                list_parts = []
                for item in v:
                    if isinstance(item, dict):
                        for ik, iv in item.items():
                            if isinstance(iv, str):
                                list_parts.append(f"{ik}: {iv}")
                            elif isinstance(iv, (int, float)):
                                list_parts.append(f"{ik}: {iv}")
                    elif isinstance(item, str):
                        list_parts.append(item)
                if list_parts:
                    items.append(f"{new_key}: {'; '.join(list_parts)}")
            elif isinstance(v, str):
                items.append(f"{new_key}: {v}")
            elif isinstance(v, (int, float)):
                items.append(f"{new_key}: {v}")
    return items


def convert_template(tpl):
    """Convert one imagejson template to our eval prompt format."""
    content = tpl.get('content', {})

    # Primary prompt: the description field is always present and reliable
    primary_prompt = tpl.get('description', '')

    # Secondary: flatten the structured content for extra detail
    # Skip keys that are already in the primary prompt or are meta
    skip_keys = {'negative_constraints', 'negative_prompt_concepts'}
    content_text_parts = []
    if isinstance(content, dict):
        for key, value in content.items():
            if key in skip_keys:
                continue
            if isinstance(value, dict):
                flat = flatten_dict(value)
                if flat:
                    content_text_parts.append(f"{key}: {'; '.join(flat)}")
            elif isinstance(value, list):
                list_strs = []
                for item in value:
                    if isinstance(item, dict):
                        flat = flatten_dict(item)
                        list_strs.append('; '.join(flat))
                    elif isinstance(item, str):
                        list_strs.append(item)
                if list_strs:
                    content_text_parts.append(f"{key}: {'; '.join(list_strs)}")
            elif isinstance(value, str):
                content_text_parts.append(f"{key}: {value}")

    # Combine: description + structured content detail
    full_prompt = primary_prompt
    if content_text_parts:
        detail_text = ' '.join(content_text_parts)
        # Add detail only if it's meaningfully different from description
        if detail_text.strip() and detail_text.strip() not in primary_prompt:
            full_prompt = f"{primary_prompt}\n\nAdditional details: {detail_text}"

    # Extract negative constraints if present
    negative = ''
    if isinstance(content, dict):
        neg = content.get('negative_constraints') or content.get('negative_prompt_concepts')
        if isinstance(neg, dict):
            negative = ', '.join(f"{k}: {v}" for k, v in neg.items())
        elif isinstance(neg, list):
            negative = ', '.join(str(x) for x in neg)
        elif isinstance(neg, str):
            negative = neg

    result = {
        'prompt': full_prompt.strip(),
        'negative': negative.strip(),
        'meta': {
            'source': 'imagejson.org',
            'template_name': tpl.get('name'),
            'template_uuid': tpl.get('uuid'),
            'category': tpl.get('category'),
            'tags': tpl.get('tags', []),
            'description': tpl.get('description'),
        },
    }

    # Also keep raw content for reference/debugging
    if content:
        result['_raw_content'] = content

    return result


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        templates = json.load(f)

    for tpl in templates:
        content = tpl.get('content')
        if not content:
            continue
        name = tpl.get('name', f"template_{tpl.get('uuid','unknown')}")
        slug = slugify(name)
        out_path = os.path.join(OUTPUT_DIR, f"{slug}.json")

        prompt = convert_template(tpl)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(prompt, f, indent=2, ensure_ascii=False)
        print(f"  {slug}.json (prompt: {len(prompt['prompt'])} chars)")

    print(f"\nWrote {len(templates)} prompt files to {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
