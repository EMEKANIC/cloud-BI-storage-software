def build_chart_data(df, max_dimensions=2, max_categories=10):
    """
    Auto-detect categorical dimensions and a numeric measure,
    then build simple aggregate charts for visualization.
    """
    def looks_like_id_or_date(col_name):
        name = col_name.lower()
        return 'id' in name or 'date' in name

    categorical_cols = [c for c in df.select_dtypes(include='object').columns
                         if not looks_like_id_or_date(c)]
    numeric_cols = [c for c in df.select_dtypes(include='number').columns
                     if not looks_like_id_or_date(c)]

    # Prefer low-cardinality categorical columns (real dimensions, not names/free text)
    categorical_cols = sorted(
        [c for c in categorical_cols if 2 <= df[c].nunique() <= 20],
        key=lambda c: df[c].nunique()
    )

    if not categorical_cols or not numeric_cols:
        return []

    # Prefer an "amount"/"total"-style numeric column as the measure
    preferred = [c for c in numeric_cols if any(k in c.lower() for k in ('total', 'amount', 'revenue', 'price'))]
    measure = preferred[0] if preferred else numeric_cols[-1]

    charts = []
    for dim in categorical_cols[:max_dimensions]:
        grouped = (df.groupby(dim)[measure].sum()
                     .sort_values(ascending=False)
                     .head(max_categories))
        charts.append({
            'type': 'bar',
            'title': f'{measure} by {dim}',
            'labels': grouped.index.astype(str).tolist(),
            'data': [round(float(v), 2) for v in grouped.values],
        })

    # One distribution chart: record count by the lowest-cardinality dimension
    # One distribution chart: record count by the lowest-cardinality dimension
    counts = df[categorical_cols[0]].value_counts().head(8)
    charts.append({
        'type': 'pie',
        'title': f'Record count by {categorical_cols[0]}',
        'labels': counts.index.astype(str).tolist(),
        'data': [int(v) for v in counts.values],
    })

    return charts