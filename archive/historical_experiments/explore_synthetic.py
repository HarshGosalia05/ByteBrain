"""Quick data exploration for the synthetic M1 dataset."""
import pandas as pd
import numpy as np

df = pd.read_csv(r'C:\Users\HET SHAH\ByteBrain\Dummy\synthetic_m1_dataset (1) (1).csv')

print("=== DUPLICATE EXAMPLE ===")
sub = df[(df['student_id'] == 'SYN000001') & (df['subject_id'] == 'SUB0007') & (df['semester_no'] == 4)]
print(sub[['internal_marks', 'mid_sem_marks', 'attendance_percentage', 'end_sem_marks']].to_string())

print("\n=== CORRELATIONS ===")
for c in ['internal_marks', 'mid_sem_marks', 'attendance_percentage', 'credits', 'semester_no']:
    corr = df[c].corr(df['end_sem_marks'])
    print(f"  {c}: {corr:.4f}")

print("\n=== INTERNAL MARKS HISTOGRAM ===")
bins = [0, 10, 15, 20, 25, 30, 35, 40]
labels = ['0-10', '10-15', '15-20', '20-25', '25-30', '30-35', '35-40']
df['internal_band'] = pd.cut(df['internal_marks'], bins=bins, labels=labels, right=False)
for band in labels:
    subset = df[df['internal_band'] == band]
    if len(subset) > 0:
        print(f"  {band}: n={len(subset):4d}, mean_end={subset['end_sem_marks'].mean():.1f}")

print("\n=== MID SEM MARKS HISTOGRAM ===")
bins2 = [0, 10, 15, 20, 25, 30, 35, 40]
df['mid_band'] = pd.cut(df['mid_sem_marks'], bins=bins2, labels=labels, right=False)
for band in labels:
    subset = df[df['mid_band'] == band]
    if len(subset) > 0:
        print(f"  {band}: n={len(subset):4d}, mean_end={subset['end_sem_marks'].mean():.1f}")

print("\n=== SEMESTER + PASS/FAIL ===")
for sem in sorted(df['semester_no'].unique()):
    sub = df[df['semester_no'] == sem]
    pass_rate = (sub['end_sem_marks'] >= 30).mean()
    print(f"  Sem {sem}: n={len(sub)}, pass_rate={pass_rate:.3f}, mean={sub['end_sem_marks'].mean():.1f}")
