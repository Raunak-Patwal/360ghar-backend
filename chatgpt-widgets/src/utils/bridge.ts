/**
 * OpenAI bridge utilities for ChatGPT widgets.
 *
 * Provides hooks and helpers for interacting with the window.openai API.
 */

import { useSyncExternalStore, useCallback } from 'react';
import type { OpenAiGlobals } from '../types/openai';

const SET_GLOBALS_EVENT_TYPE = 'openai:set_globals';

interface SetGlobalsEvent extends Event {
  detail: {
    globals: Partial<OpenAiGlobals>;
  };
}

/**
 * Hook to subscribe to a specific window.openai global value.
 * Re-renders when the value changes.
 */
export function useOpenAiGlobal<K extends keyof OpenAiGlobals>(
  key: K
): OpenAiGlobals[K] {
  return useSyncExternalStore(
    (onChange) => {
      const handleSetGlobal = (event: Event) => {
        const e = event as SetGlobalsEvent;
        if (e.detail.globals[key] !== undefined) {
          onChange();
        }
      };
      window.addEventListener(SET_GLOBALS_EVENT_TYPE, handleSetGlobal);
      return () => window.removeEventListener(SET_GLOBALS_EVENT_TYPE, handleSetGlobal);
    },
    () => window.openai[key]
  );
}

/**
 * Hook to get the current tool output data.
 */
export function useToolOutput<T = Record<string, unknown>>(): T | null {
  return useOpenAiGlobal('toolOutput') as T | null;
}

/**
 * Hook to get the current tool metadata (widget-only data).
 */
export function useToolMeta<T = Record<string, unknown>>(): T | null {
  return useOpenAiGlobal('toolResponseMetadata') as T | null;
}

/**
 * Hook to get and set widget state.
 */
export function useWidgetState<T extends Record<string, unknown>>(): [
  T | null,
  (state: T) => void
] {
  const state = useOpenAiGlobal('widgetState') as T | null;

  const setState = useCallback((newState: T) => {
    window.openai.setWidgetState(newState);
  }, []);

  return [state, setState];
}

/**
 * Hook to get the current theme.
 */
export function useTheme(): 'light' | 'dark' {
  return useOpenAiGlobal('theme');
}

/**
 * Hook to call an MCP tool.
 */
export function useCallTool() {
  return useCallback(async <T = unknown>(
    name: string,
    args: Record<string, unknown>
  ): Promise<T> => {
    const result = await window.openai.callTool<T>(name, args);
    return result.structuredContent;
  }, []);
}

/**
 * Hook to send a follow-up message.
 */
export function useSendMessage() {
  return useCallback((prompt: string) => {
    window.openai.sendFollowUpMessage({ prompt });
  }, []);
}

/**
 * Hook to request close.
 */
export function useRequestClose() {
  return useCallback(() => {
    window.openai.requestClose();
  }, []);
}
