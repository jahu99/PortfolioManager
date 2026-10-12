"""Primary BUY NEW miss classification for offline analysis."""
def classify(row: dict) -> tuple[str, str]:

    action = str(
        row.get('Observed Final Action') or ''
    ).strip().upper()

    signal = str(
        row.get('Signal') or ''
    ).strip().upper()

    entry = str(
        row.get('Entry Quality') or ''
    ).strip().upper()

    try:
        score = float(
            row.get('Investment Score')
        )
    except (TypeError, ValueError):
        score = None

    # ------------------------------------------------------------
    # Recommendation freshness
    # ------------------------------------------------------------
    #
    # A historical recommendation is only valid evidence of what
    # the Stock Momentum Agent knew at the evaluation date if it
    # was captured sufficiently close to that date.
    #
    # A stale recommendation must not be interpreted as evidence
    # that the current score/signal was low.
    #

    evaluation_date = row.get(
        'Evaluation Date'
    )

    recommendation_date = row.get(
        'Recommendation Date'
    )

    if (
        evaluation_date
        and recommendation_date
    ):
        try:
            import pandas as pd

            evaluation_ts = pd.Timestamp(
                evaluation_date
            ).normalize()

            recommendation_ts = pd.Timestamp(
                recommendation_date
            ).normalize()

            age_days = (
                evaluation_ts
                - recommendation_ts
            ).days

        except (TypeError, ValueError):
            age_days = None

        if (
            age_days is not None
            and age_days > 5
        ):
            return (
                'NO_POINT_IN_TIME_RECOMMENDATION',
                (
                    f'Latest available recommendation was '
                    f'{recommendation_ts.date().isoformat()}, '
                    f'{age_days} days before the evaluation date '
                    f'{evaluation_ts.date().isoformat()}. '
                    f'Historical scoring evidence is too stale '
                    f'to assess the BUY NEW decision.'
                )
            )

    # ------------------------------------------------------------
    # Valid point-in-time evidence
    # ------------------------------------------------------------

    if action == 'BUY NEW':
        return (
            'CAPTURED',
            'Observed completed audit action was BUY NEW.'
        )

    if (
        score is not None
        and score < 75
    ):
        return (
            'SCORE_TOO_LOW',
            (
                f'Investment Score {score:.1f} '
                f'was below the 75 threshold.'
            )
        )

    if not signal:
        return (
            'NO_RECOMMENDATION_DATA',
            'No historical recommendation or signal data was available at the evaluation date.'
        )

    if signal not in {
        'BUY',
        'STRONG BUY',
    }:
        return (
        'SIGNAL_NOT_BUY',
        (
            f'Signal was {signal}, '
            f'not BUY/STRONG BUY.'
        )
    )
    
    if entry in {
        'EXTENDED',
        'HIGHLY EXTENDED',
        'SEVERELY EXTENDED',
        'SEVERELY_EXTENDED',
    }:
        return (
            'ENTRY_QUALITY',
            f'Entry Quality was {entry}.'
        )

    if action:
        return (
            'RECOGNISED_NOT_BOUGHT',
            (
                'Basic score/signal recognition passed '
                f'but observed action was {action}.'
            )
        )

    return (
        'OTHER',
        'No completed historical audit action was available.'
    )