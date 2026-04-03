// Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
// SPDX-License-Identifier: Apache-2.0

import { useState, useCallback, useRef, useEffect } from 'react'
import {
  ChatMessage,
  ChatStreamRequest,
  StreamEvent,
  WorkflowStage,
  chatStreamService
} from '@renderer/services/ChatStreamService'
import { sanitizeAssistantContent } from '@renderer/utils/chat-content'
import { get } from 'lodash'

export interface ChatState {
  messages: ChatMessage[]
  isLoading: boolean
  currentStage?: WorkflowStage
  progress: number
  sessionId: string
  messageId: number
  error?: string
}

export interface StreamingMessage {
  id: string
  role: 'assistant'
  content: string
  isStreaming: boolean
  stage?: WorkflowStage
  progress: number
  timestamp: string
}

export const useChatStream = () => {
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: 0,
    sessionId: chatStreamService.generateSessionId(),
    messageId: -1
  })

  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null)
  const currentStreamingId = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      chatStreamService.abortStream()
    }
  }, [])

  const sendMessage = useCallback(
    async (query: string, conversation_id: number, context?: ChatStreamRequest['context']) => {
      if (!query.trim() || chatState.isLoading) return

      const userMessage: ChatMessage = {
        role: 'user',
        content: query.trim()
      }

      setChatState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        error: undefined
      }))

      setStreamingMessage(null)
      currentStreamingId.current = null

      const request: ChatStreamRequest = {
        query: query.trim(),
        conversation_id,
        context: {
          ...context,
          chat_history: [...chatState.messages, userMessage]
        },
        session_id: chatState.sessionId
      }

      try {
        await chatStreamService.sendStreamMessage(request, handleStreamEvent, handleStreamError, handleStreamComplete)
      } catch (error) {
        handleStreamError(error as Error)
      }
    },
    [chatState.messages, chatState.isLoading, chatState.sessionId]
  )

  const handleStreamEvent = useCallback((event: StreamEvent) => {
    console.log('Handling stream event:', event.type, event)

    switch (event.type) {
      case 'session_start':
        if (event.session_id) {
          setChatState((prev) => ({
            ...prev,
            sessionId: event.session_id!,
            messageId: get(event, 'assistant_message_id', prev.messageId)
          }))
        }
        break

      case 'thinking':
      case 'running': {
        const sanitizedThinkingContent = sanitizeAssistantContent(event.content)
        setChatState((prev) => ({
          ...prev,
          currentStage: event.stage,
          progress: event.progress
        }))

        setStreamingMessage((prev) => {
          if (prev && prev.stage === event.stage) {
            return {
              ...prev,
              content: sanitizedThinkingContent,
              progress: event.progress,
              timestamp: event.timestamp
            }
          }

          return {
            id: 'thinking_' + Date.now(),
            role: 'assistant',
            content: sanitizedThinkingContent,
            isStreaming: true,
            stage: event.stage,
            progress: event.progress,
            timestamp: event.timestamp
          }
        })
        break
      }

      case 'stream_chunk':
        if (!currentStreamingId.current) {
          currentStreamingId.current = 'stream_' + Date.now()
          setStreamingMessage({
            id: currentStreamingId.current,
            role: 'assistant',
            content: sanitizeAssistantContent(event.content),
            isStreaming: true,
            stage: event.stage,
            progress: event.progress,
            timestamp: event.timestamp
          })
        } else {
          setStreamingMessage((prev) => {
            if (prev) {
              const nextContent = sanitizeAssistantContent(prev.content + event.content)
              return {
                ...prev,
                content: nextContent,
                progress: event.progress,
                timestamp: event.timestamp
              }
            }
            return null
          })
        }
        break

      case 'stream_complete':
        setStreamingMessage((prev) => {
          const finalContent = sanitizeAssistantContent(prev?.content)
          if (prev && finalContent.trim()) {
            const finalMessage: ChatMessage = {
              role: 'assistant',
              content: finalContent
            }

            setChatState((currentState) => ({
              ...currentState,
              messages: [...currentState.messages, finalMessage],
              isLoading: false,
              currentStage: 'completed',
              progress: 1.0
            }))

            currentStreamingId.current = null
            return null
          }

          setChatState((currentState) => ({
            ...currentState,
            isLoading: false,
            currentStage: 'completed',
            progress: 1.0
          }))
          return null
        })
        break

      case 'completed': {
        const completedContent = sanitizeAssistantContent(event.content)
        if (completedContent.trim()) {
          const finalMessage: ChatMessage = {
            role: 'assistant',
            content: completedContent
          }

          setChatState((prev) => ({
            ...prev,
            messages: [...prev.messages, finalMessage],
            isLoading: false,
            currentStage: 'completed',
            progress: 1.0
          }))
        } else {
          setChatState((prev) => ({
            ...prev,
            isLoading: false,
            currentStage: 'completed',
            progress: 1.0
          }))
        }
        setStreamingMessage(null)
        currentStreamingId.current = null
        break
      }

      case 'fail':
        setChatState((prev) => ({
          ...prev,
          error: event.content,
          isLoading: false,
          currentStage: 'failed'
        }))
        setStreamingMessage(null)
        break

      case 'done':
        setChatState((prev) => ({
          ...prev,
          currentStage: event.stage,
          progress: event.progress
        }))
        break
    }
  }, [])

  const handleStreamError = useCallback((error: Error) => {
    console.error('Stream request error:', error)

    let errorMessage = error.message
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      errorMessage = 'Unable to connect to AI service, please check network connection and service status'
    } else if (error.name === 'AbortError') {
      errorMessage = 'Request has been cancelled'
    }

    setChatState((prev) => ({
      ...prev,
      error: errorMessage,
      isLoading: false
    }))
    setStreamingMessage(null)
    currentStreamingId.current = null
  }, [])

  const handleStreamComplete = useCallback(() => {
    console.log('Stream completed')
    setChatState((prev) => ({
      ...prev,
      isLoading: false
    }))
  }, [])

  const clearChat = useCallback(() => {
    chatStreamService.abortStream()
    setChatState({
      messages: [],
      isLoading: false,
      progress: 0,
      sessionId: chatStreamService.generateSessionId(),
      messageId: -1
    })
    setStreamingMessage(null)
    currentStreamingId.current = null
  }, [])

  const stopStreaming = useCallback(() => {
    chatStreamService.abortStream()
    setChatState((prev) => ({
      ...prev,
      isLoading: false
    }))
    setStreamingMessage(null)
  }, [])

  return {
    ...chatState,
    streamingMessage,
    sendMessage,
    clearChat,
    stopStreaming,
    setChatState
  }
}
