/**
 * WebCrypto 加密辅助：PBKDF2 派生密钥 + AES-GCM 对称加密。
 *
 * 加密 payload 格式：
 *   { encrypted: true, salt: base64, iv: base64, ciphertext: base64 }
 * 解密时用相同 password + salt 派生 key 即可解。
 *
 * PBKDF2 用 250k iterations + SHA-256，对应 2025 OWASP 推荐下限。
 */

const PBKDF2_ITERATIONS = 250000

function bufToBase64(buf) {
  const bytes = new Uint8Array(buf)
  let bin = ''
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i])
  return btoa(bin)
}

function base64ToBuf(b64) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes.buffer
}

async function deriveKey(password, salt) {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  )
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  )
}

export async function encryptPayload(plaintextStr, password) {
  if (!password) throw new Error('密码不能为空')
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt)
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(plaintextStr)
  )
  return {
    encrypted: true,
    salt: bufToBase64(salt),
    iv: bufToBase64(iv),
    ciphertext: bufToBase64(ciphertext),
  }
}

export async function decryptPayload(payload, password) {
  if (!password) throw new Error('密码不能为空')
  const salt = base64ToBuf(payload.salt)
  const iv = base64ToBuf(payload.iv)
  const ciphertext = base64ToBuf(payload.ciphertext)
  const key = await deriveKey(password, salt)
  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext
    )
    return new TextDecoder().decode(plaintext)
  } catch (e) {
    // AES-GCM 在 tag 校验失败时 throw OperationError；统一成易懂错误
    throw new Error('密码错误或数据已损坏')
  }
}

export function isEncryptedPayload(obj) {
  return Boolean(obj && obj.encrypted && obj.salt && obj.iv && obj.ciphertext)
}
