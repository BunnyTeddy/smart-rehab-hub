export const deniedMessage = 'Tài khoản này chưa có quyền bác sĩ. Liên hệ quản trị viên để được cấp quyền.';
export const unavailableMessage = 'Chưa xác minh được quyền truy cập. Kiểm tra kết nối rồi thử lại.';

export async function doctorAccess(user) {
  if (!user) return {user: null, error: '', retryable: false, loading: false};
  try {
    const token = await user.getIdTokenResult(true);
    return token.claims.role === 'doctor'
      ? {user, error: '', retryable: false, loading: false}
      : {user: null, error: deniedMessage, retryable: false, loading: false};
  } catch {
    // A failed token refresh says nothing about the account's role.
    return {user: null, error: unavailableMessage, retryable: true, loading: false};
  }
}

export function observeDoctorAccess(subscribe, update) {
  let active = true, generation = 0;
  const unsubscribe = subscribe(async user => {
    const check = ++generation;
    update({user: null, error: '', retryable: false, loading: true});
    const result = await doctorAccess(user);
    // A late response from the old account must never restore access after sign-out.
    if (active && check === generation) update(result);
  });
  return () => { active = false; generation++; unsubscribe(); };
}
