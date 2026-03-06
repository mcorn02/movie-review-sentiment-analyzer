import pandas as pd
from sklearn.metrics import f1_score

df = pd.read_csv('predictions.csv')

rows = []

for aspect, group in df.groupby('aspect'):
    f1 = f1_score(group['gold_sentiment'], group['llm_sentiment'], average='macro')
    rows.append({'aspect': aspect, 'macro_f1': round(f1, 3), 'n': len(group)})
summary = pd.DataFrame(rows).sort_values('macro_f1')
print(summary.to_string(index=False))