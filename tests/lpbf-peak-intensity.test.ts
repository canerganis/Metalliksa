import assert from 'node:assert/strict';
import test from 'node:test';

import { calculatePeakLaserIntensity } from '../src/types/lpbfDataFoundation.js';

test('calculates Gaussian peak irradiance from a 1/e2 beam diameter', () => {
  assert.equal(calculatePeakLaserIntensity(285, 67), 16.167);
});
