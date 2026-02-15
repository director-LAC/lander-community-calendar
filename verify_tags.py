from build_calendar import get_categories, CATEGORY_WEIGHTS

def test_tagging():
    # Test Case 1: Festival
    title = "International Climbers Fest"
    source = "Community"
    tags = get_categories(title, source)
    print(f"Title: '{title}' -> Tags: {tags}")
    
    assert "Community & Social" in tags, "Failed to add Community tag to Festival"
    assert "Sports & Outdoors" in tags, "Failed to identify Sports tag"

    # Test Case 2: Farmer's Market
    title = "Lander Valley Farmers Market"
    tags = get_categories(title, source)
    print(f"Title: '{title}' -> Tags: {tags}")
    assert "Food & Drink" in tags, "Failed Market -> Food rule"
    assert "Community & Social" in tags, "Failed Market -> Community rule"

    # Test Case 3: Al Anon (Regression Test)
    title = "Al Anon Meeting"
    tags = get_categories(title, source)
    print(f"Title: '{title}' -> Tags: {tags}")
    assert "Government & Civic" not in tags, "Regression: Al Anon flagged as Govt"
    assert "Community & Social" in tags, "Al Anon should be Community"

    print("\n✅ All Tagging Logic Verified!")

if __name__ == "__main__":
    test_tagging()
