/**
 * Side service replies via ctx.response({ data: payload }).
 * MessageBuilder delivers that envelope to the watch — unwrap once here.
 */
export function sidePayload(res) {
  if (res == null) return {}
  if (typeof res === 'object' && res.data !== undefined && res.data !== null) {
    return res.data
  }
  return res
}

/** Voice side service nests hub JSON under env.data; routing fields sit on env. */
export function hubFromSide(res) {
  const env = sidePayload(res)
  const body =
    env &&
    env.data !== undefined &&
    typeof env.data === 'object' &&
    !Array.isArray(env.data)
      ? env.data
      : env
  return { env, body }
}
