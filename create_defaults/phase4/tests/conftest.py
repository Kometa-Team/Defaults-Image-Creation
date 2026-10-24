"""One session-owned native composition corpus shared by M3/M4 bounded tests."""
import pytest

from create_defaults.bulk.lifecycle import composition
from create_defaults.bulk.lifecycle.previews import CompositionTrial
from create_defaults.phase4.tests import composition_samples as samples


@pytest.fixture(scope='session')
def composed():
    trials=[]
    class Values(dict):
        def __missing__(self,kind):
            trial=CompositionTrial();trials.append(trial)
            if kind=='overlay':ctx=samples.overlays(trial)
            elif kind=='family':ctx=samples.family(trial)
            else:ctx=samples.poster(trial,{'playlist':'Playlist','genre':'Genre','network':'Network'}[kind],paired=kind=='network')
            requests=[samples.exception(ctx.candidate)] if kind in {'playlist','genre'} else []
            evidence=composition.compose(ctx,trial,exceptions=requests)
            self[kind]=(trial,ctx,evidence,requests)
            return self[kind]
    values=Values();values.replays={}
    try:
        yield values
    finally:
        for trial in reversed(trials):trial.close()


@pytest.fixture(scope='session')
def transaction_seed():
    from create_defaults.phase4.tests.transaction_samples import reviewed
    with CompositionTrial() as trial:
        ctx=samples.poster(trial,'Genre')
        yield reviewed(trial,ctx,exceptions=[samples.exception(ctx.candidate)])
