"""Diagnostic-only records for unresolved labels; never production receipts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
from people_workspaces import atomic_json, reject_links


def write_review(directory, record, renderer):
    directory=Path(directory)
    reject_links(directory)
    directory.mkdir(parents=True,exist_ok=True)
    record=dict(record,validated=False,publication_authorized=False,purpose='unicode-review-required-v1')
    if record.get('font') not in renderer.metrics:
        record['diagnostic_preview_error']='Failed non-text style has no label font'
        atomic_json(directory/'review-required.json',record)
        return record
    try:
        font=ImageFont.truetype(str(renderer.font_dir/record['font']),60,layout_engine=ImageFont.Layout.BASIC)
        image=Image.new('RGB',(2000,420),'#202020')
        draw=ImageDraw.Draw(image)
        draw.text((30,25),'DIAGNOSTIC ONLY / REVIEW REQUIRED / DO NOT PUBLISH',fill='orange')
        draw.text((30,110),record['original_name'],font=font,fill='white')
        metadata=PngImagePlugin.PngInfo()
        metadata.add_text('Status','UNVALIDATED DIAGNOSTIC - DO NOT PUBLISH')
        image.save(directory/'REVIEW-ONLY.png',pnginfo=metadata)
        image.close()
        record['diagnostic_preview']='REVIEW-ONLY.png'
    except (OSError,ValueError,KeyError) as error:
        record['diagnostic_preview_error']=str(error)
    atomic_json(directory/'review-required.json',record)
    return record
