// Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
// SPDX-License-Identifier: Apache-2.0

import { useState, useCallback, useRef, useEffect } from 'react'
import { useDispatch } from 'react-redux'
import {
  ChatMessage,
  ChatStreamRequest,
  StreamEvent,
  WorkflowStage,
  chatStreamService
} from '@renderer/services/ChatStreamService'
import { sanitizeAssistantContent } from '@renderer/utils/chat-content'
import { get } from 'lodash'
import {
  addBackgroundGeneratingConversation,
  removeBackgroundGeneratingConversation,
  setActiveChatMessages,
  appendActiveChatMessage
} from '@renderer/store/chat-history'

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
  const dispatch = useDispatch()
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: 0,
    sessionId: chatStreamService.generateSessionId(),
    messageId: -1
  })

  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null)
  const currentStreamingId = useRef<string | null>(null)
  const currentConversationId = useRef<number | null>(null)
  const isInitialized = useRef(false)

  // Note: We don't abort streams on unmount to allow background generation
  // when navigating between pages. Streams are aborted per-conversation via
  // abortStream(conversationId) when explicitly stopped by user.
  useEffect(() => {
    // Cleanup is intentionally not done here to allow background generation
    // The conversation will be removed from backgroundGeneratingConversations
    // when stream completes or errors via handleStreamComplete/handleStreamError
  }, [])

  const sendMessage = useCallback(
    async (query: string, conversation_id: number, context?: ChatStreamRequest['context']) => {
      if (!query.trim() || chatState.isLoading) return

      const userMessage: ChatMessage = {
        role: 'user',
        content: query.trim()
      }

      // Store user message in Redux for persistence
      dispatch(appendActiveChatMessage({ conversationId: conversation_id, message: userMessage }))

      setChatState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        error: undefined
      }))

      setStreamingMessage(null)
      currentStreamingId.current = null
      currentConversationId.current = conversation_id

      // Dispatch to Redux to track this conversation as background generating
      dispatch(addBackgroundGeneratingConversation(conversation_id))

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
    [chatState.messages, chatState.isLoading, chatState.sessionId, dispatch]
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
        // Remove from background generating list
        if (currentConversationId.current !== null) {
          dispatch(removeBackgroundGeneratingConversation(currentConversationId.current))
          currentConversationId.current = null
        }
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

  const handleStreamError = useCallback(
    (error: Error) => {
      console.error('Stream request error:', error)

      let errorMessage = error.message
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        errorMessage = 'Unable to connect to AI service, please check network connection and service status'
      } else if (error.name === 'AbortError') {
        errorMessage = 'Request has been cancelled'
      }

      // Remove from background generating list
      if (currentConversationId.current !== null) {
        dispatch(removeBackgroundGeneratingConversation(currentConversationId.current))
        currentConversationId.current = null
      }

      setChatState((prev) => ({
        ...prev,
        error: errorMessage,
        isLoading: false
      }))
      setStreamingMessage(null)
      currentStreamingId.current = null
    },
    [dispatch]
  )

  const handleStreamComplete = useCallback(() => {
    console.log('Stream completed')
    // Remove from background generating list
    if (currentConversationId.current !== null) {
      dispatch(removeBackgroundGeneratingConversation(currentConversationId.current))
      currentConversationId.current = null
    }
    setChatState((prev) => ({
      ...prev,
      isLoading: false
    }))
  }, [dispatch])

  const clearChat = useCallback(() => {
    chatStreamService.abortAllStreams()
    // Remove all conversations from background generating list
    if (currentConversationId.current !== null) {
      dispatch(removeBackgroundGeneratingConversation(currentConversationId.current))
      currentConversationId.current = null
    }
    setChatState({
      messages: [],
      isLoading: false,
      progress: 0,
      sessionId: chatStreamService.generateSessionId(),
      messageId: -1
    })
    setStreamingMessage(null)
    currentStreamingId.current = null
  }, [dispatch])

  const stopStreaming = useCallback(() => {
    chatStreamService.abortAllStreams()
    // Remove from background generating list
    if (currentConversationId.current !== null) {
      dispatch(removeBackgroundGeneratingConversation(currentConversationId.current))
      currentConversationId.current = null
    }
    setChatState((prev) => ({
      ...prev,
      isLoading: false
    }))
    setStreamingMessage(null)
  }, [dispatch])

  return {
    ...chatState,
    streamingMessage,
    sendMessage,
    clearChat,
    stopStreaming,
    setChatState,
    syncMessagesToRedux: (conversationId: number, messages: ChatMessage[]) => {
      dispatch(setActiveChatMessages({ conversationId, messages }))
    }
  }
}
