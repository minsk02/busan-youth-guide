"""문서 삽입용 그림 생성. 선택 도구: Pillow (앱 실행에는 필요 없음)."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = Path('C:/Windows/Fonts/malgun.ttf')


def canvas(width, height):
    image = Image.new('RGB', (width, height), 'white')
    return image, ImageDraw.Draw(image)


def text(draw, xy, label, size=23, fill='#243746'):
    draw.multiline_text(xy, label, font=ImageFont.truetype(str(FONT), size), fill=fill, spacing=8, align='center', anchor='mm')


def box(draw, rect, label, fill='#eef5f7'):
    draw.rounded_rectangle(rect, radius=8, fill=fill, outline='#7896a3', width=2)
    text(draw, ((rect[0]+rect[2])/2, (rect[1]+rect[3])/2), label)


def arrow(draw, start, end):
    draw.line([start, end], fill='#5b7682', width=3)
    x, y = end
    if x > start[0]:
        draw.polygon([(x,y),(x-12,y-7),(x-12,y+7)], fill='#5b7682')
    elif x < start[0]:
        draw.polygon([(x,y),(x+12,y-7),(x+12,y+7)], fill='#5b7682')
    else:
        draw.polygon([(x,y),(x-7,y-12),(x+7,y-12)], fill='#5b7682')


def actor(draw, x, y, label):
    draw.ellipse((x-17,y,x+17,y+34), outline='#334f60', width=3)
    draw.line([(x,y+34),(x,y+86)], fill='#334f60', width=3)
    draw.line([(x-30,y+55),(x+30,y+55)], fill='#334f60', width=3)
    draw.line([(x,y+86),(x-25,y+117)], fill='#334f60', width=3)
    draw.line([(x,y+86),(x+25,y+117)], fill='#334f60', width=3)
    text(draw, (x,y+145), label, 20)


image, draw = canvas(1400, 720)
text(draw, (700,45), '부산청년 프로그램 찾기 전체 구조', 30)
box(draw,(40,160,230,275),'사용자 화면\nHTML / JS')
box(draw,(310,160,500,275),'Flask API\n요청·오류 처리')
box(draw,(590,90,840,205),'조건 해석\nbackend/ai.py')
box(draw,(1010,90,1320,205),'OpenAI\ngpt-4o-mini')
box(draw,(590,285,840,400),'검색·추천·비교\nprograms.py')
box(draw,(1010,300,1320,415),'SQLite\nprograms / sync_runs')
box(draw,(40,535,230,645),'운영 담당자\nmanage.py sync')
box(draw,(400,535,750,645),'데이터 수집·정규화\ndata_source.py')
box(draw,(1010,535,1320,645),'부산 청년지원 API\ngetYouthSupProg')
for start,end in [((230,215),(310,215)),((500,180),(590,145)),((840,145),(1010,145)),((500,255),(590,340)),((840,345),(1010,345)),((230,590),(400,590)),((750,590),(1010,590)),((750,535),(1080,415))]:
    arrow(draw,start,end)
image.save(HERE/'architecture.png')

image, draw = canvas(1300, 850)
text(draw, (650,40), '유스케이스 다이어그램', 30)
draw.rectangle((290,100,950,805), outline='#7896a3', width=2)
text(draw,(620,140),'부산청년 프로그램 찾기',25)
actor(draw,120,285,'사용자')
actor(draw,120,635,'운영 담당자')
actor(draw,1120,220,'OpenAI')
actor(draw,1120,610,'공공데이터 API')
for y,label in [(235,'UC-001 자연어 검색'),(355,'UC-002 맞춤 추천'),(475,'UC-003 프로그램 비교'),(595,'UC-004 상세·출처'),(730,'UC-005 데이터 수집')]:
    draw.ellipse((400,y-40,840,y+40),fill='#f1f6f8',outline='#7896a3',width=2)
    text(draw,(620,y),label,23)
    draw.line([(150,350 if y<700 else 700),(400,y)],fill='#5b7682',width=2)
draw.line([(840,235),(1090,275)],fill='#5b7682',width=2)
draw.line([(840,730),(1090,665)],fill='#5b7682',width=2)
image.save(HERE/'use-cases.png')

image, draw = canvas(1250, 850)
text(draw,(625,40),'주요 화면 구성안',30)
box(draw,(70,95,1180,155),'부산청년 프로그램 찾기                                      데이터 출처', '#f7f9f8')
box(draw,(70,190,560,390),'서비스 소개\n저장 건수 / 신청기간 내 건수')
box(draw,(600,190,1180,390),'질문 입력\n질문 예시 / 조건 읽기 / 안내')
box(draw,(70,430,1180,565),'분야 / 키워드 / 대상 / 신청기간\n현재 신청기간 필터 / 이 조건으로 검색')
box(draw,(70,600,600,760),'검색 결과·맞춤 추천\n프로그램 카드 / 상세 / 비교 선택')
box(draw,(650,600,1180,760),'상세 창·비교 창\n대상 / 기간 / 기관 / 출처')
text(draw,(625,810),'구성도이며 실제 브라우저 캡처는 아님',18,'#677c86')
image.save(HERE/'screens.png')
