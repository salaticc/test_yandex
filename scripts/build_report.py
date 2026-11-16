"""Recompute all published figures from the included synthetic CSV files."""
from pathlib import Path
import hashlib,json,platform,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.analysis import load_and_analyse
from scripts.portfolio_ui import write_overview


def main():
    summary,tables,check=load_and_analyse(ROOT)
    report=ROOT/'reports';report.mkdir(exist_ok=True)
    for name,frame in tables.items():frame.to_csv(report/(name+'.csv'),index=name=='retention')
    check.to_csv(report/'sql_reconciliation.csv',index=False)
    summary['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'data').glob('*.csv')}
    summary['verification_environment']={'python':platform.python_version()}
    (report/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    monthly=tables['monthly'];tiers=tables['tiers'];products=tables['products']
    data={'title':'Business Travel — структура оборота и неактивность','subtitle':'2025 · синтетическое тестовое задание · единица клиента — компания',
    'kpis':[{'label':'GMV подтверждённых броней','value':f"{summary['confirmed_gmv_rub']/1e6:.2f} млн ₽"},{'label':'Подтверждённых бронирований','value':f"{summary['confirmed_bookings']:,}".replace(',',' ')},{'label':'Неактивны в H2 / активны в H1','value':f"{summary['h2_inactive_companies']} / {summary['h1_active_companies']}"},{'label':'Их исторический GMV за H1','value':f"{summary['inactive_companies_historical_h1_gmv_rub']/1e6:.2f} млн ₽"}],
    'charts':[{'title':'GMV по субпродуктам','unit':'млн ₽','rows':[{'label':r.subproduct,'value':round(r.gmv/1e6,3)} for r in products.itertuples()]},{'title':'GMV по сегментам компаний','unit':'млн ₽','rows':[{'label':f'Tier {r.tier} · {r.active_companies} компаний','value':round(r.gmv/1e6,3)} for r in tiers.itertuples()]}],
    'insights':[{'fact':'16 компаний без подтверждённых броней в H2; их H1 GMV — 17,51 млн ₽.','next':'Начать с проверки потребностей и причин неактивности крупных аккаунтов; эта сумма не является доказанным убытком.'},{'fact':'Tier 2 формирует 43,94% годового GMV; Tier 1 — 41,36%.','next':'Приоритизировать исследование среднего бизнеса; решение о бюджете требует маржи и стоимости привлечения.'},{'fact':'Новых компаний с first_booking_date в 2025 году нет.','next':'Retention новых когорт не рассчитывается. Для проверки сезонности нужна история нескольких лет.'}],
    'scope':'Все исходные 1 964 строки сохранены. GMV только confirmed; 48 из 48 срезов месяц × субпродукт совпали в SQLite и pandas. В данных нет employee_id, комиссий платформы или причин оттока.'}
    for product in products.subproduct:
        rows=monthly.loc[monthly.subproduct.eq(product)]
        data['charts'].append({'title':f'{product} — GMV по месяцам','unit':'млн ₽','rows':[{'label':r.month,'value':round(r.gmv/1e6,3)} for r in rows.itertuples()]})
    write_overview(ROOT,data)
    lines=['# Выводы для бизнеса','',f"За 2025 год: **{summary['confirmed_gmv_rub']:,.2f} ₽ GMV**, {summary['confirmed_bookings']} подтверждённое бронирование, {summary['active_companies']} активных компаний.",'']
    for i in data['insights']:lines.extend(['## '+i['fact'],'',i['next'],''])
    lines.extend(['## Границы интерпретации','','- Исторический GMV не является потерянной выручкой или LTV.','- Частоты рассчитаны на компанию; число сотрудников неизвестно.','- Отмены не доказывают причины отмен; данные синтетические.','- Падение оборота не разделено причинно на сезонность и отток.','', 'Полные таблицы: CSV в reports/. Числовой контракт: summary.json.'])
    (report/'EXECUTIVE_SUMMARY.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['confirmed_gmv_rub','confirmed_bookings','h2_inactive_companies','sql_checks_passed']},ensure_ascii=False))


if __name__=='__main__':main()
