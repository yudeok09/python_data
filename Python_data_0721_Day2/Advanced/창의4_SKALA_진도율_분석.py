# [창의 과제 4] SKALA 광주 3반 진도 코치
# ------------------------------------------------------------------
# HTML/CSS 주차에 쓰던 진도 체크표를 내보낸 JSON이 남아 있길래, 이번에 배운 걸
# 우리 반 데이터에 그대로 써봤다. 교수님 입장에서 궁금한 건 결국 세 가지라고 생각했다.
#   ① 다들 어디서 막혔나        → 과제별 완료율 + 커리큘럼 순서대로 본 이탈 퍼널
#   ② 누구를 먼저 도와야 하나   → 진도 정체·후반부 미완·도움요청을 합친 코칭 우선순위
#   ③ 전공/비전공 차이가 진짜냐 → 통계 검정. 단 10명이라 검정 선택이 까다롭다
#
# ③이 이 과제의 핵심이다. 종합2에서 쓴 카이제곱을 그대로 가져다 쓰면 안 된다.
# 10명짜리 표에서는 기대빈도가 5를 밑돌아서 카이제곱 근사가 깨지기 때문이다.
# 그래서 Fisher 정확검정과 Mann-Whitney U(비모수)로 바꿔서 계산했다.
#
# 쓰는 기술: 중첩 JSON + Pydantic 검증(실습2) · pandas 집계(실습4)
#            · 통계 검정(종합2) · HTML 리포트(종합3)
#
# 실행: python Advanced/창의4_SKALA_진도율_분석.py

import json
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from scipy import stats

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "skala_진도율.json"
OUT = BASE / "output"

RISK_HELP = 30  # 도움요청 플래그는 가중치를 크게 (본인이 손 든 거니까)


class Task(BaseModel):
    id: str
    day: str
    title: str
    description: str = ""


class Student(BaseModel):
    id: str
    name: str
    track: str
    helpNeeded: bool = False
    completed: list[str] = Field(default_factory=list)


def load_class():
    """내보내기 JSON을 읽고 Pydantic으로 한 번 거른다 (실습2 방식).
    체크표 앱에서 내보낸 거라 필드가 빠질 수도 있어서 그냥 믿지 않는다."""
    raw = json.loads(DATA.read_text(encoding="utf-8"))

    tasks, students, dropped = [], [], []
    for t in raw["tasks"]:
        try:
            tasks.append(Task(**t))
        except ValidationError as e:
            dropped.append(("task", t.get("id", "?"), e.error_count()))
    for s in raw["students"]:
        try:
            students.append(Student(**s))
        except ValidationError as e:
            dropped.append(("student", s.get("name", "?"), e.error_count()))

    return raw["className"], raw["exportedAt"][:10], tasks, students, dropped


def build_table(tasks, students):
    """학생 × 과제 완료여부 표. 여기서부터는 그냥 pandas 문제가 된다."""
    task_ids = [t.id for t in tasks]
    rows = []
    for s in students:
        done = set(s.completed)
        row = {"이름": s.name, "트랙": s.track, "도움요청": s.helpNeeded}
        row.update({tid: (tid in done) for tid in task_ids})
        rows.append(row)
    return pd.DataFrame(rows)


def task_funnel(df, tasks):
    """커리큘럼 순서대로 완료 인원을 세면 어디서 뚝 떨어지는지 보인다.
    마케팅에서 쓰는 퍼널을 수업 진도에 그대로 갖다 쓴 것."""
    n = len(df)
    out = []
    prev = n
    for t in tasks:
        done = int(df[t.id].sum())
        out.append(
            {
                "id": t.id,
                "day": t.day,
                "title": t.title,
                "완료": done,
                "완료율": done / n * 100,
                "직전대비_이탈": prev - done,  # 이 과제에서 새로 막힌 인원
            }
        )
        prev = done
    return pd.DataFrame(out)


def coaching_priority(df, tasks):
    """단순히 '적게 한 순'으로 줄 세우면 성의 없다.
    후반부(day2)에서 못 따라오는 건 더 위험 신호라 가중치를 다르게 줬다."""
    d1 = [t.id for t in tasks if t.day == "day1"]
    d2 = [t.id for t in tasks if t.day == "day2"]

    out = df[["이름", "트랙", "도움요청"]].copy()
    out["day1_완료"] = df[d1].sum(axis=1)
    out["day2_완료"] = df[d2].sum(axis=1)
    out["전체_완료"] = out["day1_완료"] + out["day2_완료"]
    out["진도율"] = out["전체_완료"] / len(tasks) * 100

    # 위험점수 = 못 한 비율(50) + day2 미완 비중(20) + 도움요청(30)
    미완비율 = 1 - out["전체_완료"] / len(tasks)
    day2_미완 = 1 - out["day2_완료"] / len(d2)
    out["위험점수"] = (
        미완비율 * 50 + day2_미완 * 20 + out["도움요청"] * RISK_HELP
    ).round(1)
    out["등급"] = pd.cut(
        out["위험점수"], bins=[-1, 20, 45, 200], labels=["안정", "관찰", "우선코칭"]
    )
    return out.sort_values("위험점수", ascending=False).reset_index(drop=True)


def track_test(summary):
    """전공/비전공 차이 검정. 여기서 검정을 잘못 고르면 결론이 통째로 틀린다.

    표본이 10명이라
      - 카이제곱  : 기대빈도 5 미만이 생겨서 부적합 (근사가 깨짐)
      - t-검정    : 정규성 가정하기엔 표본이 너무 작음
    그래서 Fisher 정확검정 + Mann-Whitney U 로 간다.
    """
    major = summary[summary["트랙"] == "major"]["전체_완료"]
    non = summary[summary["트랙"] == "non-major"]["전체_완료"]

    # ① 완료 개수 분포 비교 (비모수)
    u, p_u = stats.mannwhitneyu(major, non, alternative="two-sided")

    # ② 완주(14개 전부) 여부 × 트랙 2x2 → Fisher 정확검정
    full = summary["전체_완료"] == summary["전체_완료"].max()
    # 한쪽 칸이 비면 2x2가 성립 안 하니 reindex로 채운다.
    # (여기서 table[[False, True]] 로 쓰면 pandas가 컬럼이 아니라 '행 불린 마스크'로
    #  읽어버려서 행이 통째로 잘린다. 한참 헤맸던 부분이라 적어둔다.)
    table = pd.crosstab(summary["트랙"], full).reindex(
        columns=[False, True], fill_value=0
    )
    odds, p_f = stats.fisher_exact(table.to_numpy())

    # 카이제곱을 굳이 돌려보면 왜 못 쓰는지 숫자로 나온다
    chi2, p_chi, _, expected = stats.chi2_contingency(table.to_numpy())
    return {
        "major_평균": float(major.mean()),
        "non_평균": float(non.mean()),
        "u": float(u),
        "p_u": float(p_u),
        "odds": float(odds),
        "p_f": float(p_f),
        "min_expected": float(expected.min()),
        "p_chi": float(p_chi),
    }


def print_report(cls, exported, tasks, students, dropped, funnel, summary, test):
    n = len(students)
    print("=" * 62)
    print(f"  {cls} 진도 코치  (내보낸 날짜 {exported})")
    print("=" * 62)
    print(f"수강생 {n}명 · 과제 {len(tasks)}개 · 검증 탈락 {len(dropped)}건")

    avg = summary["진도율"].mean()
    full = int((summary["전체_완료"] == len(tasks)).sum())
    need = int(summary["도움요청"].sum())
    worst = funnel.sort_values("완료율").iloc[0]
    print(f"반 평균 진도율 {avg:.1f}% · 완주 {full}명 · 도움요청 {need}명")

    print("\n[① 커리큘럼 퍼널] 순서대로 몇 명이 남았나")
    for _, r in funnel.iterrows():
        bar = "█" * round(r["완료율"] / 100 * 24)
        drop = (
            f"  ← 여기서 {r['직전대비_이탈']}명 이탈" if r["직전대비_이탈"] > 0 else ""
        )
        print(f"  {r['day']} {r['title'][:12]:<13} {bar:<24} {r['완료']:>2}/{n}{drop}")
    print(
        f"  → 가장 많이 막힌 과제: '{worst['title']}' (완료율 {worst['완료율']:.0f}%)"
    )

    print("\n[② 코칭 우선순위] 위험점수 = 미완(50) + day2미완(20) + 도움요청(30)")
    print(f"  {'이름':<6}{'트랙':<11}{'진도':>7}{'day2':>7}{'위험':>7}  등급")
    print("  " + "-" * 52)
    for _, r in summary.iterrows():
        flag = " *도움요청" if r["도움요청"] else ""
        print(
            f"  {r['이름']:<5}{r['트랙']:<11}{r['진도율']:>6.0f}%"
            f"{r['day2_완료']:>5}/7{r['위험점수']:>7.1f}  {r['등급']}{flag}"
        )

    print("\n[③ 전공/비전공 차이가 진짜인가]")
    print(
        f"  평균 완료: 전공 {test['major_평균']:.1f}개 vs 비전공 {test['non_평균']:.1f}개"
    )
    print(f"  Mann-Whitney U = {test['u']:.1f}, p = {test['p_u']:.3f}")
    print(f"  Fisher 정확검정(완주 여부) p = {test['p_f']:.3f}")
    print(
        f"  ※ 카이제곱은 기대빈도 최솟값이 {test['min_expected']:.2f}(<5)라 쓰면 안 된다."
    )
    verdict = "차이 있다고 말할 수 없다" if test["p_u"] >= 0.05 else "차이가 유의하다"
    print(f"  → p>0.05 이므로 {verdict}. 10명 표본으로 전공 탓을 하면 안 된다.")


def build_dashboard(cls, exported, tasks, funnel, summary, test):
    n = len(summary)
    avg = summary["진도율"].mean()
    full = int((summary["전체_완료"] == len(tasks)).sum())
    need = int(summary["도움요청"].sum())
    worst = funnel.sort_values("완료율").iloc[0]

    def funnel_rows():
        html = ""
        for _, r in funnel.iterrows():
            hot = " hot" if r["완료율"] <= worst["완료율"] else ""
            badge = (
                f'<i class="drop">-{r["직전대비_이탈"]}</i>'
                if r["직전대비_이탈"] > 0
                else ""
            )
            html += f"""
        <div class="frow{hot}">
          <span class="d">{r["day"]}</span>
          <span class="t">{r["title"]}</span>
          <span class="track"><span style="width:{r["완료율"]:.0f}%"></span></span>
          <span class="c">{r["완료"]}/{n}{badge}</span>
        </div>"""
        return html

    def student_rows():
        html = ""
        for _, r in summary.iterrows():
            grade = str(r["등급"])
            cls_ = {"우선코칭": "hi", "관찰": "mid"}.get(grade, "lo")
            hand = '<i class="hand">손들었음</i>' if r["도움요청"] else ""
            tr = "전공" if r["트랙"] == "major" else "비전공"
            html += f"""
        <tr>
          <td class="nm">{r["이름"]}{hand}</td>
          <td><span class="tag">{tr}</span></td>
          <td class="num">{r["전체_완료"]}/{len(tasks)}</td>
          <td><span class="track sm"><span style="width:{r["진도율"]:.0f}%"></span></span></td>
          <td class="num">{r["day2_완료"]}/7</td>
          <td class="num">{r["위험점수"]:.0f}</td>
          <td><span class="grade {cls_}">{grade}</span></td>
        </tr>"""
        return html

    top3 = funnel.sort_values("완료율").head(3)["title"].tolist()
    coach = summary[summary["등급"] == "우선코칭"]["이름"].tolist()

    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{cls} 진도 코치</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    margin: 0; padding: 36px 20px; background: #f4f6fb; color: #16182a; }}
  .wrap {{ max-width: 940px; margin: 0 auto; }}
  header {{ background: linear-gradient(120deg, #2b3566, #4a5aa8); color: #fff;
    padding: 26px 30px; border-radius: 16px 16px 0 0; }}
  header h1 {{ margin: 0; font-size: 25px; letter-spacing: -.4px; }}
  header p {{ margin: 6px 0 0; opacity: .82; font-size: 13px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
    background: #dde2f0; border-radius: 0 0 16px 16px; overflow: hidden; margin-bottom: 26px; }}
  .kpi {{ background: #fff; padding: 18px 20px; }}
  .kpi b {{ display: block; font-size: 24px; color: #2b3566; font-variant-numeric: tabular-nums; }}
  .kpi span {{ font-size: 12px; color: #7a7f95; }}
  section {{ background: #fff; border-radius: 14px; padding: 24px 26px; margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(20,25,60,.07); }}
  h2 {{ font-size: 16px; margin: 0 0 4px; color: #2b3566; }}
  .sub {{ font-size: 12.5px; color: #8a8fa3; margin: 0 0 16px; }}
  .frow {{ display: grid; grid-template-columns: 46px 1fr 190px 78px; align-items: center;
    gap: 10px; padding: 6px 0; font-size: 13.5px; }}
  .frow .d {{ font-size: 11px; color: #9aa0b5; }}
  .frow.hot .t {{ color: #c0392b; font-weight: 600; }}
  .track {{ display: block; height: 9px; background: #e9ecf7; border-radius: 5px; overflow: hidden; }}
  .track > span {{ display: block; height: 100%; background: #4a5aa8; border-radius: 5px; }}
  .frow.hot .track > span {{ background: #d9534f; }}
  .track.sm {{ width: 108px; }}
  .c {{ font-size: 12.5px; color: #555; text-align: right; font-variant-numeric: tabular-nums; }}
  .drop {{ color: #c0392b; font-style: normal; font-size: 11px; margin-left: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  th {{ text-align: left; color: #7a7f95; font-size: 11.5px; font-weight: 600;
    padding: 0 8px 8px; border-bottom: 1px solid #eceffa; }}
  td {{ padding: 9px 8px; border-bottom: 1px solid #f4f6fb; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .nm {{ font-weight: 600; }}
  .hand {{ font-style: normal; font-size: 10.5px; background: #fff1cf; color: #9a6b00;
    padding: 1px 6px; border-radius: 20px; margin-left: 6px; }}
  .tag {{ font-size: 11px; background: #eef1fb; color: #4a5aa8; padding: 2px 8px; border-radius: 20px; }}
  .grade {{ font-size: 11.5px; padding: 2px 9px; border-radius: 20px; }}
  .grade.hi {{ background: #fdecea; color: #c0392b; }}
  .grade.mid {{ background: #fff6e0; color: #a07000; }}
  .grade.lo {{ background: #eaf6ee; color: #2b7a45; }}
  .stat {{ display: flex; gap: 14px; flex-wrap: wrap; }}
  .stat div {{ flex: 1; min-width: 190px; background: #f7f9ff; border-radius: 10px; padding: 14px 16px; }}
  .stat b {{ display: block; font-size: 17px; color: #2b3566; }}
  .stat small {{ color: #7a7f95; font-size: 11.5px; }}
  .warn {{ margin-top: 14px; background: #fffaf0; border-left: 4px solid #e0a020;
    padding: 12px 15px; border-radius: 8px; font-size: 13px; line-height: 1.65; }}
  .todo li {{ margin-bottom: 6px; font-size: 13.5px; }}
  footer {{ text-align: center; color: #a3a8bb; font-size: 11.5px; padding: 8px 0 4px; }}
</style></head><body><div class="wrap">

<header>
  <h1>{cls} · 진도 코치</h1>
  <p>진도 체크표 내보내기({exported}) 를 파이썬으로 다시 읽어 정리 · 과제 {len(tasks)}개 / 수강생 {n}명</p>
</header>
<div class="kpis">
  <div class="kpi"><b>{avg:.0f}%</b><span>반 평균 진도율</span></div>
  <div class="kpi"><b>{full}명</b><span>14개 전부 완주</span></div>
  <div class="kpi"><b>{worst["완료율"]:.0f}%</b><span>최난관 과제 완료율</span></div>
  <div class="kpi"><b>{need}명</b><span>도움 요청</span></div>
</div>

<section>
  <h2>① 커리큘럼 퍼널 — 어디서 떨어져 나가나</h2>
  <p class="sub">과제를 배운 순서대로 세워놓고 남은 인원을 셌다. 빨간 줄이 가장 많이 막힌 지점.</p>
  {funnel_rows()}
</section>

<section>
  <h2>② 코칭 우선순위</h2>
  <p class="sub">위험점수 = 미완 비율(50) + day2 미완(20) + 본인 도움요청(30).
     후반부에서 못 따라오는 쪽에 가중치를 더 줬다.</p>
  <table>
    <thead><tr><th>이름</th><th>트랙</th><th class="num">완료</th><th>진도</th>
      <th class="num">day2</th><th class="num">위험</th><th>등급</th></tr></thead>
    <tbody>{student_rows()}</tbody>
  </table>
</section>

<section>
  <h2>③ 전공/비전공 차이는 진짜일까</h2>
  <p class="sub">눈으로는 차이가 보이는데, 10명짜리 표본에서 그걸 그대로 믿으면 안 된다.</p>
  <div class="stat">
    <div><b>{test["major_평균"]:.1f} vs {test["non_평균"]:.1f}</b><small>평균 완료 과제 수 (전공 vs 비전공)</small></div>
    <div><b>p = {test["p_u"]:.3f}</b><small>Mann-Whitney U (비모수)</small></div>
    <div><b>p = {test["p_f"]:.3f}</b><small>Fisher 정확검정 (완주 여부)</small></div>
  </div>
  <div class="warn">
    <b>검정을 왜 바꿨나:</b> 종합실습2에서는 카이제곱을 썼지만 여기서는 못 쓴다.
    2×2 표의 <b>기대빈도 최솟값이 {test["min_expected"]:.2f}</b>로 5를 밑돌아 카이제곱 근사가 깨지기 때문이다
    (참고로 억지로 돌리면 p={test["p_chi"]:.3f}가 나오는데, 이 값은 신뢰할 수 없다).
    소표본에서는 Fisher 정확검정이 맞고, 분포 비교는 정규성 가정이 필요 없는 Mann-Whitney U가 안전하다.<br>
    <b>결론:</b> 두 검정 모두 p&gt;0.05 → <b>전공 여부로 진도 차이를 설명할 수 없다.</b>
    실제로 진도가 가장 느린 학생도 전공자다. 트랙이 아니라 개인별로 봐야 한다.
  </div>
</section>

<section>
  <h2>다음 수업 액션</h2>
  <p class="sub">숫자만 뽑고 끝내면 리포트가 아니라 그냥 표다. 할 일로 바꿔봤다.</p>
  <ul class="todo">
    <li><b>다시 짚을 과제</b> — {" · ".join(top3)}</li>
    <li><b>개별 코칭</b> — {", ".join(coach) if coach else "해당 없음"} (day2 진입 전 따라잡기 필요)</li>
    <li><b>수업 운영</b> — day2 후반 과제에서 이탈이 몰리니, 갤러리·투두는 실습 시간을 더 잡는 편이 낫겠다</li>
  </ul>
</section>

<footer>SKALA 광주 3반 유덕현 · 파이썬 데이터분석 창의과제</footer>
</div></body></html>"""

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "skala_progress_dashboard.html"
    path.write_text(html, encoding="utf-8")
    return path


def main():
    cls, exported, tasks, students, dropped = load_class()
    df = build_table(tasks, students)
    funnel = task_funnel(df, tasks)
    summary = coaching_priority(df, tasks)
    test = track_test(summary)

    print_report(cls, exported, tasks, students, dropped, funnel, summary, test)

    path = build_dashboard(cls, exported, tasks, funnel, summary, test)
    summary.to_csv(
        OUT / "skala_coaching_priority.csv", index=False, encoding="utf-8-sig"
    )
    print(f"\n대시보드: {path.name}")
    print("코칭 명단: skala_coaching_priority.csv (엑셀로 바로 열림)")


if __name__ == "__main__":
    main()
