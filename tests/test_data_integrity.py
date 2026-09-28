import pytest
import pandas as pd
from srs_logging_utils import sanitize_df

def test_sanitize_df_basic_cleaning():
    """Verify that valid data passes through and invalid values are coerced."""
    raw_data = {
        'id': ['1', '2', None],
        'interval': ['10', 'bad_data', '5'],
        'easiness': [2.5, '3.0', None]
    }
    df = pd.DataFrame(raw_data)
    schema = {'id': 'str', 'interval': 'int', 'easiness': 'float'}
    
    clean_df = sanitize_df(df, schema)
    
    # Assertions
    assert clean_df['interval'].iloc[1] == 0       # 'bad_data' coerced to 0
    assert clean_df['easiness'].iloc[2] == 0.0     # None coerced to 0.0
    assert clean_df['id'].iloc[2] == ''            # None was coerced to an empty string
    assert clean_df['interval'].dtype == 'int64'

def test_sanitize_df_missing_columns():
    """Verify function doesn't crash if a column in schema is missing from DF."""
    df = pd.DataFrame({'id': ['1']})
    schema = {'id': 'str', 'non_existent_col': 'int'}
    
    # This should run without error
    clean_df = sanitize_df(df, schema)
    assert 'id' in clean_df.columns
    assert len(clean_df.columns) == 1