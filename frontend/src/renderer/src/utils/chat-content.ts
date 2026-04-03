const THINK_OPEN_TAG = '<think'
const THINK_CLOSE_TAG = '</think'

function isPartialThinkTag(fragment: string): boolean {
  return THINK_OPEN_TAG.startsWith(fragment) || THINK_CLOSE_TAG.startsWith(fragment)
}

export function sanitizeAssistantContent(content: string | null | undefined): string {
  if (!content) return ''

  const source = String(content)
  const lowerSource = source.toLowerCase()
  const result: string[] = []

  let index = 0
  let insideThinkBlock = false

  while (index < source.length) {
    if (insideThinkBlock) {
      const closeIndex = lowerSource.indexOf(THINK_CLOSE_TAG, index)
      if (closeIndex === -1) {
        break
      }

      const closeEnd = source.indexOf('>', closeIndex)
      if (closeEnd === -1) {
        break
      }

      index = closeEnd + 1
      insideThinkBlock = false
      continue
    }

    const nextTagStart = source.indexOf('<', index)
    if (nextTagStart === -1) {
      result.push(source.slice(index))
      break
    }

    result.push(source.slice(index, nextTagStart))

    const remainingLower = lowerSource.slice(nextTagStart)
    if (remainingLower.startsWith(THINK_OPEN_TAG)) {
      const openEnd = source.indexOf('>', nextTagStart)
      if (openEnd === -1) {
        break
      }

      index = openEnd + 1
      insideThinkBlock = true
      continue
    }

    if (remainingLower.startsWith(THINK_CLOSE_TAG)) {
      const closeEnd = source.indexOf('>', nextTagStart)
      if (closeEnd === -1) {
        break
      }

      index = closeEnd + 1
      continue
    }

    const possiblePartialTag = remainingLower.match(/^<\/?[a-z/]*/)?.[0] || ''
    if (possiblePartialTag.length > 1 && isPartialThinkTag(possiblePartialTag)) {
      break
    }

    result.push(source[nextTagStart])
    index = nextTagStart + 1
  }

  return result.join('')
}
