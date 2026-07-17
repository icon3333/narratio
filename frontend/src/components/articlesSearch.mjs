/**
 * Decide whether submitting the search form will change the active query.
 *
 * @param {number} page
 * @param {string} activeSearch
 * @param {string} nextSearch
 * @returns {boolean}
 */
export function shouldStartSearchLoading(page, activeSearch, nextSearch) {
  return page !== 1 || activeSearch !== nextSearch;
}
