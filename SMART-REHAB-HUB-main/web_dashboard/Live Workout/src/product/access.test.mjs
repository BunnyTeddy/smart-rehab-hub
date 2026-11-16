import {test} from 'node:test';
import assert from 'node:assert/strict';
import {doctorAccess, observeDoctorAccess, deniedMessage, unavailableMessage} from './access.js';

test('only a current doctor claim opens the workspace', async () => {
  for (const role of [undefined, 'patient', 'hub', 'doctor']) {
    const user = {getIdTokenResult: async refresh => {assert.equal(refresh, true); return {claims: {role}};}};
    const result = await doctorAccess(user);
    assert.equal(result.user, role === 'doctor' ? user : null);
    assert.equal(result.error, role === 'doctor' ? '' : deniedMessage);
  }
});

test('failed refresh blocks access but offers retry instead of claiming missing permission', async () => {
  const result = await doctorAccess({getIdTokenResult: async () => {throw new Error('network');}});
  assert.equal(result.user, null);
  assert.equal(result.error, unavailableMessage);
  assert.equal(result.retryable, true);
});

test('late doctor response cannot restore access after sign-out', async () => {
  let callback, finish;
  const updates = [];
  const stop = observeDoctorAccess(cb => {callback = cb; return () => {};}, value => updates.push(value));
  const pending = callback({getIdTokenResult: () => new Promise(resolve => {finish = resolve;})});
  await callback(null);
  finish({claims:{role:'doctor'}});
  await pending;
  assert.equal(updates.at(-1).user, null);
  assert.equal(updates.at(-1).loading, false);
  stop();
});

test('unmounted verification cannot update the next screen', async () => {
  let callback, finish, unsubscribed = false;
  const updates = [];
  const stop = observeDoctorAccess(cb => {callback = cb; return () => {unsubscribed = true;};}, value => updates.push(value));
  const pending = callback({getIdTokenResult: () => new Promise(resolve => {finish = resolve;})});
  stop();
  finish({claims:{role:'doctor'}});
  await pending;
  assert.equal(updates.length, 1);
  assert.equal(unsubscribed, true);
});
