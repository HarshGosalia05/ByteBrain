import { test } from "node:test"
import assert from "node:assert/strict"

import { translate } from "./translate.ts"
import { DICTIONARIES } from "./dictionaries.ts"

test("English is the default language and returns English text", () => {
  assert.equal(translate("Dashboard", "en"), "Dashboard")
  assert.equal(translate("Settings", "en"), "Settings")
  assert.equal(translate("Academic", "en"), "Academic")
  assert.equal(translate("Report Card", "en"), "Report Card")
})

test("Hindi translations match prompt requirements and dictionaries", () => {
  assert.equal(translate("Dashboard", "hi"), "डैशबोर्ड")
  assert.equal(translate("Academic", "hi"), "शैक्षणिक")
  assert.equal(translate("Report Card", "hi"), "प्रगति पत्र")
  assert.equal(translate("Subjects", "hi"), "विषय")
  assert.equal(translate("Attendance", "hi"), "उपस्थिति")
  assert.equal(translate("Timetable", "hi"), "समय सारणी")
  assert.equal(translate("ML Insights", "hi"), "एमएल अंतर्दृष्टि")
  assert.equal(translate("Profile", "hi"), "प्रोफ़ाइल")
  assert.equal(translate("Notifications", "hi"), "सूचनाएं")
  assert.equal(translate("Settings", "hi"), "सेटिंग्स")

  // Prompt required examples
  assert.equal(
    translate("Next-semester risk prediction", "hi"),
    "अगले सेमेस्टर के जोखिम का पूर्वानुमान",
  )
  assert.equal(translate("Faculty Review", "hi"), "फैकल्टी समीक्षा")
  assert.equal(translate("Confirm", "hi"), "पुष्टि करें")
  assert.equal(translate("Dismiss", "hi"), "अस्वीकार करें")
})

test("Gujarati translations match prompt requirements and dictionaries", () => {
  assert.equal(translate("Dashboard", "gu"), "ડેશબોર્ડ")
  assert.equal(translate("Academic", "gu"), "શૈક્ષણિક")
  assert.equal(translate("Report Card", "gu"), "રિપોર્ટ કાર્ડ")
  assert.equal(translate("Subjects", "gu"), "વિષયો")
  assert.equal(translate("Attendance", "gu"), "હાજરી")
  assert.equal(translate("Timetable", "gu"), "સમયપત્રક")
  assert.equal(translate("ML Insights", "gu"), "એમએલ આંતરદ્રષ્ટિ")
  assert.equal(translate("Profile", "gu"), "પ્રોફાઇલ")
  assert.equal(translate("Notifications", "gu"), "સૂચનાઓ")
  assert.equal(translate("Settings", "gu"), "સેટિંગ્સ")

  // Prompt required examples
  assert.equal(
    translate("Next-semester risk prediction", "gu"),
    "આગામી સેમેસ્ટરના જોખમની આગાહી",
  )
  assert.equal(translate("Faculty Review", "gu"), "ફેકલ્ટી સમીક્ષા")
  assert.equal(translate("Confirm", "gu"), "પુષ્ટિ કરો")
  assert.equal(translate("Dismiss", "gu"), "નકારો")
})

test("English -> Hindi -> Gujarati -> English language transition consistency", () => {
  const keys = [
    "Attendance simulator",
    "Current attendance",
    "KenexAI Assistant",
    "Ask a question...",
    "Confirm",
    "Dismiss",
  ]

  for (const key of keys) {
    // English
    const enText = translate(key, "en")
    assert.equal(enText, key)

    // Hindi
    const hiText = translate(key, "hi")
    assert.notEqual(hiText, "")
    assert.notEqual(hiText, enText)

    // Gujarati
    const guText = translate(key, "gu")
    assert.notEqual(guText, "")
    assert.notEqual(guText, enText)

    // Back to English
    const roundTripEn = translate(key, "en")
    assert.equal(roundTripEn, key)
  }
})

test("Fallback behavior returns English or key when key is missing in target language", () => {
  // Unknown key in Hindi falls back to default text or key itself
  assert.equal(translate("NonExistentKey123", "hi"), "NonExistentKey123")
  assert.equal(translate("NonExistentKey123", "hi", "Custom Fallback"), "Custom Fallback")

  // Unknown key in Gujarati falls back to default text or key itself
  assert.equal(translate("NonExistentKey123", "gu"), "NonExistentKey123")
  assert.equal(translate("NonExistentKey123", "gu", "Custom Fallback"), "Custom Fallback")
})

test("Factual data, marks, percentages, IDs and database values are not altered", () => {
  assert.equal(translate("STU000001", "hi"), "STU000001")
  assert.equal(translate("92.5%", "gu"), "92.5%")
  assert.equal(translate("8.84", "hi"), "8.84")
  assert.equal(translate("CS301", "gu"), "CS301")
  assert.equal(translate("2026-08-14", "hi"), "2026-08-14")
  assert.equal(translate("Aarav Patel", "gu"), "Aarav Patel")
})
