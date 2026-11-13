from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'Textures'
OUT.mkdir(exist_ok=True)
image = Image.new('RGB', (1600, 2260), (244, 241, 230))
draw = ImageDraw.Draw(image)
regular = 'C:/Windows/Fonts/YuGothM.ttc'
bold = 'C:/Windows/Fonts/YuGothB.ttc'


def text(position, value, size, fill=(29, 34, 37), strong=False, anchor=None):
    font = ImageFont.truetype(bold if strong else regular, size)
    draw.text(position, value, font=font, fill=fill, anchor=anchor)


text((800, 180), '入学承諾書', 180, strong=True, anchor='mt')
draw.line((110, 445, 1490, 445), fill=(38, 45, 48), width=6)
text((130, 615), '氏名：', 66)
draw.line((355, 705, 1460, 705), fill=(105, 105, 99), width=3)
text((130, 850), '生年月日：', 66)
text((600, 850), '　　 年　　 月　　 日', 66)
draw.line((575, 945, 1460, 945), fill=(105, 105, 99), width=3)
text((130, 1110), '保護者同意：', 64)
for x, label in ((755, 'はい'), (1140, 'YES')):
    draw.rectangle((x, 1123, x + 62, 1185), outline=(28, 36, 39), width=5)
    text((x + 90, 1102), label, 72, strong=True)
for y in (1425, 1550, 1675, 1800):
    draw.line((130, y, 1460, y), fill=(134, 131, 120), width=3)
draw.rounded_rectangle((1140, 1915, 1460, 2155), radius=12, outline=(166, 40, 29), width=9)
text((1300, 1925), '承認', 120, fill=(166, 40, 29), strong=True, anchor='mt')
image.save(OUT / 'T_AdmissionAgreement_BaseColor.png')
print(OUT / 'T_AdmissionAgreement_BaseColor.png')
