import pytest
from srs_logging_utils import calculate_srs_metrics

def test_srs_metrics_mastered():
    """Test that a quality score of 6 forces mastery settings."""
    ivl, reps, ef = calculate_srs_metrics(quality=6, interval=10.0, easiness=2.5, repetition=3)
    
    assert ivl == 21
    assert reps == 4
    assert ef == 2.5

def test_srs_metrics_again():
    """Test that an 'Again' score resets repetitions and interval."""
    ivl, reps, ef = calculate_srs_metrics(quality=0, interval=10.0, easiness=2.5, repetition=3)
    
    assert ivl == 1
    assert reps == 0
    # Formula check: 2.5 + (0.1 - (5) * (0.08 + 5 * 0.02)) = 2.5 - 0.8 = 1.7
    assert round(ef, 2) == 1.70

def test_srs_metrics_good_first_rep():
    """Test standard progression on the very first review."""
    ivl, reps, ef = calculate_srs_metrics(quality=4, interval=0.0, easiness=2.5, repetition=0)
    
    assert ivl == 1
    assert reps == 1
    assert ef == 2.5 # Ease factor stays stable on a 'Good' score
    
def test_srs_metrics_easy():
    """Test that an 'Easy' score increases the easiness factor."""
    # We set repetition=2 so it bypasses the hardcoded '6' and hits the multiplication logic
    ivl, reps, ef = calculate_srs_metrics(quality=5, interval=6.0, easiness=2.5, repetition=2)
    
    # 6.0 * 2.5 = 15.0. 
    assert ivl == 15 
    assert reps == 3
    assert ef > 2.5