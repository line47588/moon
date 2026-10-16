#!/usr/bin/env python3
"""Builds moon.json (วันพระ) and holiday.json (วันหยุด) for the CYD calendar page.

Run by the GitHub Action in line47588/moon (weekly), so the files cover the years ahead
without anyone uploading them by hand:
  - วันพระ and every lunar date: computed with pythaidate (CsDate, the Suriyayatra
    lunisolar calendar the official Thai calendar uses). Checked against the 2025 and
    2026 files made by hand: all 98 วันพระ dates match.
  - holidays: Google's public "Holidays in Thailand" calendar (government holidays,
    substitute days and special days once the cabinet announces them), plus the
    Buddhist holidays computed here (Google lists them only once announced).

Output entries keep the old format the firmware parses:
  {"UID": "20260103", "DESCRIPTION": "วันเสาร์ ขึ้น 15 ค่ำ เดือนยี่ (2) ปีมะเส็ง", "SUMMARY": "วันพระ"}
Range: December of last year to December of next year.

    python gen_calendar.py [out_dir]
"""
import datetime
import json
import re
import sys
import urllib.request

from pythaidate import CsDate, to_julianday

GOOGLE_ICS = 'https://calendar.google.com/calendar/ical/th.th%23holiday%40group.v.calendar.google.com/public/basic.ics'

WEEKDAYS = ['วันจันทร์', 'วันอังคาร', 'วันพุธ', 'วันพฤหัสบดี', 'วันศุกร์', 'วันเสาร์', 'วันอาทิตย์']
MONTHS = {1: 'อ้าย', 2: 'ยี่', 3: 'สาม', 4: 'สี่', 5: 'ห้า', 6: 'หก', 7: 'เจ็ด', 8: 'แปด', 9: 'เก้า',
          10: 'สิบ', 11: 'สิบเอ็ด', 12: 'สิบสอง', 88: 'แปดหลัง'}
ANIMALS = ['ชวด', 'ฉลู', 'ขาล', 'เถาะ', 'มะโรง', 'มะเส็ง', 'มะเมีย', 'มะแม', 'วอก', 'ระกา', 'จอ', 'กุน']

# Google's long official names -> the short names the 320 px screen shows
SHORT_NAMES = [
    ('ชดเชย', 'วันหยุดชดเชย'),
    ('ปีใหม่', 'วันขึ้นปีใหม่'), ('ขื้นปีใหม่', 'วันขึ้นปีใหม่'),
    ('สิ้นปี', 'วันสิ้นปี'),
    ('มาฆบูชา', 'วันมาฆบูชา'), ('วิสาขบูชา', 'วันวิสาขบูชา'), ('อาสาฬหบูชา', 'วันอาสาฬหบูชา'),
    ('เข้าพรรษา', 'วันเข้าพรรษา (ราชการ)'), ('ออกพรรษา', 'วันออกพรรษา'),
    ('จักรี', 'วันจักรี'), ('สงกรานต์', 'วันสงกรานต์'), ('แรงงาน', 'วันแรงงาน (เอกชน)'),
    ('ฉัตรมงคล', 'วันฉัตรมงคล'), ('พืชมงคล', 'วันพืชมงคล (ราชการ)'),
    ('สุทิดา', 'วันเฉลิมฯ พระบรมราชินี'), ('มหาวชิราลงกรณ', 'วันเฉลิมฯ พระวชิรเกล้าเจ้าอยู่หัว'),
    ('สิริกิติ์', 'วันแม่'), ('สวรรคต', 'วันนวมินทรมหาราช'), ('ปิยมหาราช', 'วันปิยมหาราช'),
    ('พระบรมราชสมภพ', 'วันพ่อ'), ('รัฐธรรมนูญ', 'วันรัฐธรรมนูญ'),
    ('พิเศษ', 'วันหยุดพิเศษ (ครม.)'), ('ราชการ', 'วันหยุดพิเศษ (ครม.)'),
]


def cs(d):
    return CsDate.fromjulianday(to_julianday(d.year, d.month, d.day))


def describe(d):
    """'วันเสาร์ ขึ้น 15 ค่ำ เดือนยี่ (2) ปีมะเส็ง'"""
    c = cs(d)
    phase, num = ('ขึ้น', c.day) if c.day <= 15 else ('แรม', c.day - 15)
    # the animal year turns at ขึ้น 1 ค่ำ เดือนห้า: months 1-4 early in the year still
    # belong to last year's animal (เดือนอ้าย in December is already this year's)
    animal_year = d.year - 1 if c.month in (1, 2, 3, 4) and d.month <= 6 else d.year
    animal = ANIMALS[(animal_year - 4) % 12]
    return f'{WEEKDAYS[d.weekday()]} {phase} {num} ค่ำ เดือน{MONTHS[c.month]} ({c.month}) ปี{animal}'


def days(first, last):
    d = first
    while d <= last:
        yield d
        d += datetime.timedelta(days=1)


def wanphra(first, last):
    for d in days(first, last):
        c, n = cs(d), cs(d + datetime.timedelta(days=1))
        if c.day in (8, 15, 23) or n.day == 1:  # ขึ้น 8, ขึ้น 15, แรม 8, the last day (แรม 14/15)
            yield d


def buddhist_holidays(year):
    """มาฆบูชา, วิสาขบูชา, อาสาฬหบูชา, เข้าพรรษา of a Gregorian year (one month later in
    a year with the second 8th month, เดือนแปดหลัง)."""
    first, last = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    lunar = {d: cs(d) for d in days(first, last)}
    leap = any(c.month == 88 for c in lunar.values())
    want = {'วันมาฆบูชา': 4 if leap else 3, 'วันวิสาขบูชา': 7 if leap else 6, 'วันอาสาฬหบูชา': 88 if leap else 8}
    out = {}
    for name, month in want.items():
        for d, c in lunar.items():
            if c.month == month and c.day == 15:
                out[d] = name
                if name == 'วันอาสาฬหบูชา':
                    out[d + datetime.timedelta(days=1)] = 'วันเข้าพรรษา (ราชการ)'
                break
    return out


def google_holidays():
    req = urllib.request.Request(GOOGLE_ICS, headers={'User-Agent': 'cyd-calendar/1.0'})
    text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8').replace('\r\n ', '').replace('\r\n', '\n')
    out = {}
    for ev in re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', text, re.S):
        m = re.search(r'DTSTART;VALUE=DATE:(\d{8})', ev)
        s = re.search(r'^SUMMARY:(.*)$', ev, re.M)
        desc = re.search(r'^DESCRIPTION:(.*)$', ev, re.M)
        if not m or not s:
            continue
        if not desc or 'วันหยุดนักขัตฤกษ์' not in desc.group(1):
            continue  # "วันสำคัญ" (Valentine's, Chinese New Year...) are not days off
        name = s.group(1).replace('​', '').strip()
        short = next((v for k, v in SHORT_NAMES if k in name), name[:30])
        out[datetime.datetime.strptime(m.group(1), '%Y%m%d').date()] = short
    return out


def entry(d, summary):
    return {'UID': d.strftime('%Y%m%d'), 'DESCRIPTION': describe(d), 'SUMMARY': summary}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    today = datetime.date.today()
    first, last = datetime.date(today.year - 1, 12, 1), datetime.date(today.year + 1, 12, 31)

    moon = [entry(d, 'วันพระ') for d in wanphra(first, last)]

    hol = {}
    for y in range(first.year, last.year + 1):
        hol.update(buddhist_holidays(y))
    try:
        hol.update(google_holidays())  # Google's names win on the same day
    except Exception as e:  # keep the computed ones; the old file stays if this fails twice
        print('Google holidays:', e, file=sys.stderr)
    holidays = [entry(d, hol[d]) for d in sorted(hol) if first <= d <= last]

    for name, data in (('moon.json', moon), ('holiday.json', holidays)):
        with open(f'{out_dir}/{name}', 'w', encoding='utf-8', newline='\n') as f:
            f.write('[\n' + ',\n'.join('  ' + json.dumps(x, ensure_ascii=False) for x in data) + '\n]\n')
        print(f'{name}: {len(data)} entries, {data[0]["UID"]}..{data[-1]["UID"]}')


if __name__ == '__main__':
    main()
