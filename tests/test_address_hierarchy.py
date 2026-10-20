# -*- coding: utf-8 -*-
"""
Tests for hierarchical address resolution (1-line, 2-line, 3-line)
and standard geographical components (city, state, country, pincode).
"""
import pytest
from automation.browser import resolve_address_components, DEFAULT_CANDIDATE


def test_resolve_address_components_single_line():
    """Verify single line returns full address for line 1 and empty for lines 2 & 3."""
    cand = {
        "address": "123 Main St, Apt 4, City, State, Country",
        "address_2_line1": "123 Main St",
        "address_2_line2": "Apt 4",
        "address_3_line1": "123 Main",
        "address_3_line2": "St",
        "address_3_line3": "Apt 4",
    }
    l1, l2, l3 = resolve_address_components(has_line2=False, has_line3=False, cand=cand)
    assert l1 == "123 Main St, Apt 4, City, State, Country"
    assert l2 == ""
    assert l3 == ""


def test_resolve_address_components_two_lines_from_env():
    """Verify 2-line resolution respects explicit address_2_line1 and line2."""
    cand = {
        "address": "Full Address",
        "address_2_line1": "Line 1 Content",
        "address_2_line2": "Line 2 Content",
    }
    l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=False, cand=cand)
    assert l1 == "Line 1 Content"
    assert l2 == "Line 2 Content"
    assert l3 == ""


def test_resolve_address_components_two_lines_fallback_split():
    """Verify 2-line fallback splitting when line1/line2 keys are not explicitly set."""
    cand = {
        "address": "Part A, Part B, Part C, Part D, Part E",
    }
    l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=False, cand=cand)
    assert l1 == "Part A, Part B, Part C"
    assert l2 == "Part D, Part E"
    assert l3 == ""


def test_resolve_address_components_three_lines_from_env():
    """Verify 3-line resolution respects explicit address_3_line1, line2, line3."""
    cand = {
        "address": "Full Address",
        "address_3_line1": "L1",
        "address_3_line2": "L2",
        "address_3_line3": "L3",
    }
    l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=True, cand=cand)
    assert l1 == "L1"
    assert l2 == "L2"
    assert l3 == "L3"


def test_resolve_address_components_three_lines_fallback_split():
    """Verify 3-line fallback splitting when line1/line2/line3 are not explicitly set."""
    cand = {
        "address": "Part 1, Part 2, Part 3, Part 4, Part 5",
    }
    l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=True, cand=cand)
    assert l1 == "Part 1, Part 2"
    assert l2 == "Part 3"
    assert l3 == "Part 4"


def test_default_candidate_contains_address_keys():
    """Verify DEFAULT_CANDIDATE has all address hierarchy keys."""
    expected_keys = [
        "address",
        "address_2_line1",
        "address_2_line2",
        "address_3_line1",
        "address_3_line2",
        "address_3_line3",
        "city",
        "state",
        "country",
        "pincode",
    ]
    for k in expected_keys:
        assert k in DEFAULT_CANDIDATE, f"Missing key {k} in DEFAULT_CANDIDATE"
