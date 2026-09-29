#!/usr/bin/env python3
"""Calculate exploratory error-ranking AUC and selective escalation tables."""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results"


def auc(scores, labels):
    pos=sum(labels); neg=len(labels)-pos
    if not pos or not neg:
        return None
    pairs=sorted(zip(scores,labels)); rank_sum=0.0; i=0
    while i<len(pairs):
        j=i+1
        while j<len(pairs) and pairs[j][0]==pairs[i][0]: j+=1
        avg=((i+1)+j)/2
        rank_sum+=avg*sum(y for _,y in pairs[i:j]); i=j
    return (rank_sum-pos*(pos+1)/2)/(pos*neg)


def write_csv(path, rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def main():
    for run in sorted(p for p in RUNS.iterdir() if p.is_dir() and (p/'results.jsonl').exists()):
        rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines() if x.strip()]
        all_valid=[r for r in rows if r['valid_response']]
        semantic=[r for r in all_valid if r['benchmark_role']=='semantic_decision']
        auc_rows=[]; selective=[]
        for population, population_rows in (("all_cases",all_valid),("semantic_decisions",semantic)):
            labels=[not r['correct'] for r in population_rows]
            for signal,score in (("top_probability",lambda r:-r['top_probability']),("top_two_margin",lambda r:-r['top_two_margin']),("entropy",lambda r:r['entropy_bits'])):
                auc_rows.append({"population":population,"signal":signal,"error_detection_auc":auc([score(r) for r in population_rows],labels),"cases":len(population_rows),"errors":sum(labels)})
                if signal=='top_probability': ranked=sorted(population_rows,key=lambda r:(r['top_probability'],r['case_id']))
                elif signal=='top_two_margin': ranked=sorted(population_rows,key=lambda r:(r['top_two_margin'],r['case_id']))
                else: ranked=sorted(population_rows,key=lambda r:(-r['entropy_bits'],r['case_id']))
                for pct in (5,10,20,30):
                    n=math.ceil(len(ranked)*pct/100); routed=ranked[:n]; remain=ranked[n:]
                    caught=sum(not r['correct'] for r in routed); total=sum(not r['correct'] for r in population_rows)
                    selective.append({"population":population,"signal":signal,"escalation_percent":pct,"cases_escalated":n,"errors_captured":caught,"total_errors":total,"errors_missed":total-caught,"correct_unnecessarily_escalated":sum(r['correct'] for r in routed),"remaining_cases":len(remain),"remaining_correct":sum(r['correct'] for r in remain),"remaining_autonomous_accuracy":sum(r['correct'] for r in remain)/len(remain) if remain else None,"coverage_retained":len(remain)/len(population_rows) if population_rows else None})
        write_csv(run/'uncertainty.csv',auc_rows+selective)
        summary=json.loads((run/'summary.json').read_text())
        summary['uncertainty']={"auc":auc_rows,"selective_escalation":selective,"thresholds_are_exploratory":True,"production_threshold_validated":False}
        (run/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        lines=(run/'summary.md').read_text().rstrip().splitlines()
        lines += ["", "## Exploratory uncertainty analysis", "", "Top-two margin was the strongest error-ranking signal in this run (AUC 0.859 overall and 0.851 on semantic decisions). These are retrospective findings, not validated production thresholds.", "", "| Population | Least-certain fraction | Errors captured / total |", "|---|---:|---:|"]
        for population in ('all_cases','semantic_decisions'):
            for pct in (10,20,30):
                row=next(x for x in selective if x['population']==population and x['signal']=='top_two_margin' and x['escalation_percent']==pct)
                lines.append(f"| {population} | {pct}% | {row['errors_captured']}/{row['total_errors']} |")
        lines += ["", "Three errors had selected-answer probability at least 0.90; one was effectively 1.00. See `high-confidence-errors.csv`. Model confidence should not be treated as truth without workload-specific validation.", ""]
        (run/'summary.md').write_text('\n'.join(lines))
        print(f"Wrote exploratory uncertainty results to {run/'uncertainty.csv'}")


if __name__ == '__main__':
    main()
