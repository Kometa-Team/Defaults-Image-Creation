"""Deterministic display-only Unicode policy shared by daily and bulk rendering.

Identity and filenames never pass through normalization or substitution. Fonts
are selected for a whole label, so a combining cluster is never split across fonts.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import unicodedata

POLICY_VERSION = 'people-unicode-inter-v1'
INTER_SHA256 = '164414f0aacbe98a7e64addc43f7b3bfd2e32f7b90e101feeab227f14c371bda'
STYLE_FONTS = {'bw':'Comfortaa-Medium.ttf','rainier':'Comfortaa-Medium.ttf',
               'signature':'Fuggles-Regular.ttf','diiivoy':'Inter-Light.ttf','diiivoycolor':'Inter-Light.ttf'}
FALLBACK_FONTS = ('Inter-Light.ttf',)
SUBSTITUTIONS = {'\u02bb':'\u2019'}
POLICY = dict(version=POLICY_VERSION,fonts=STYLE_FONTS,fallbacks=FALLBACK_FONTS,
              substitutions=SUBSTITUTIONS,fallback_unit='whole-label',inter_sha256=INTER_SHA256,publication_authorized=False)
POLICY_SHA256 = hashlib.sha256(json.dumps(POLICY,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


@dataclass(frozen=True)
class LabelResolution:
    original_name: str
    filename: str
    style: str
    display_label: str
    font: str
    resolution_method: str
    policy_sha256: str
    attempts: tuple
    substitutions: tuple = ()

    def record(self):
        return asdict(self)


class ReviewRequired(ValueError):
    def __init__(self, record):
        self.record = record
        super().__init__('Unicode label requires review: '+record['original_name']+' / '+record['style'])


def resolve_label(original_name, filename, style, metrics, *, lettering=None):
    if style not in STYLE_FONTS:
        raise ValueError('Unknown text style')
    primary = STYLE_FONTS[style]
    raw = original_name if lettering is None else lettering
    text = raw if style == 'signature' else raw.upper()
    attempts=[]

    def accept(label,font,method,substitutions=()):
        if not label or not label.strip():
            return None
        try:
            for line in label.splitlines():
                metrics[font].glyphs(line)
                metrics[font].layout(line,100)
        except ValueError as error:
            attempts.append(dict(font=font,method=method,text=label,error=str(error)))
            return None
        attempts.append(dict(font=font,method=method,text=label,supported=True))
        return LabelResolution(original_name,filename,style,label,font,method,POLICY_SHA256,tuple(attempts),tuple(substitutions))

    value=accept(text,primary,'original')
    if value:return value
    equivalents=[]
    for form in ('NFC','NFD'):
        candidate=unicodedata.normalize(form,text)
        if candidate!=text and candidate not in equivalents:
            equivalents.append(candidate)
            value=accept(candidate,primary,'normalized')
            if value:return value
    candidate=text
    changes=[]
    for old,new in SUBSTITUTIONS.items():
        if old in candidate and ord(old) not in metrics[primary].cmap:
            candidate=candidate.replace(old,new)
            changes.append(dict(original=old,replacement=new,rule='U+02BB-to-U+2019-v1'))
    if changes:
        value=accept(candidate,primary,'substituted',changes)
        if value:return value
    for font in FALLBACK_FONTS:
        if font!=primary:
            value=accept(text,font,'fallback-font')
            if value:return value
    raise ReviewRequired(dict(original_name=original_name,filename=filename,style=style,
        font=primary,display_label=None,resolution_method='review-required',policy_sha256=POLICY_SHA256,
        codepoints=[f'U+{ord(c):04X}' for c in text],attempts=attempts,publication_authorized=False))
