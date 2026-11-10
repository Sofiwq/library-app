import pytest

def test_dummy():
    assert True

def test_fine_calculation():
    days = 10
    fine = min(days * 10, 500)
    assert fine == 100

def test_fine_max_cap():
    days = 100
    fine = min(days * 10, 500)
    assert fine == 500
