Feature: Sentiment indicators API
  The sentiment indicators endpoint should return labeled indicators
  for each ticker, and support deletion by ticker.

  Scenario: No snapshots returns empty list
    Given the sentiment indicators data store is empty
    When I request sentiment indicators
    Then the response status code is 200
    And the response is an empty list

  Scenario: Snapshot is labeled bullish/neutral/bearish
    Given the sentiment indicators data store has a snapshot for "RELIANCE.NS" with 30d return 0.05
    When I request sentiment indicators for "RELIANCE"
    Then the response status code is 200
    And the response contains ticker "RELIANCE.NS"
    And the indicator "d30" is "bullish"

  Scenario: Delete by ticker returns deleted count
    Given the sentiment indicators data store has 3 rows for ticker "BP"
    When I delete sentiment indicators for ticker "BP"
    Then the response status code is 200
    And the deleted count is 3
