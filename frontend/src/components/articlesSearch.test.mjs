import assert from "node:assert/strict";
import test from "node:test";

import { shouldStartSearchLoading } from "./articlesSearch.mjs";

test("does not start loading when submitting the already-active search on page one", () => {
  assert.equal(shouldStartSearchLoading(1, "inflation", "inflation"), false);
});

test("starts loading when the submitted search changes", () => {
  assert.equal(shouldStartSearchLoading(1, "inflation", "rates"), true);
});

test("starts loading when an existing search is resubmitted from a later page", () => {
  assert.equal(shouldStartSearchLoading(2, "inflation", "inflation"), true);
});
