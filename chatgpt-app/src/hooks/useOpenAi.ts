import { useState, useEffect, useCallback, useSyncExternalStore } from 'react';
import type { OpenAiGlobals, WidgetState } from '../types/openai';

const SET_GLOBALS_EVENT_TYPE = 'openai:set_globals';

interface SetGlobalsEvent extends CustomEvent {
  detail: {
    globals: Partial<OpenAiGlobals>;
  };
}

/**
 * Hook to subscribe to window.openai global values
 * Automatically re-renders when the value changes
 */
export function useOpenAiGlobal<K extends keyof OpenAiGlobals>(
  key: K
): OpenAiGlobals[K] | undefined {
  return useSyncExternalStore(
    (onChange) => {
      const handleSetGlobal = (event: Event) => {
        const customEvent = event as SetGlobalsEvent;
        const value = customEvent.detail?.globals?.[key];
        if (value !== undefined) {
          onChange();
        }
      };

      window.addEventListener(SET_GLOBALS_EVENT_TYPE, handleSetGlobal, {
        passive: true,
      });

      return () => {
        window.removeEventListener(SET_GLOBALS_EVENT_TYPE, handleSetGlobal);
      };
    },
    () => window.openai?.[key]
  );
}

/**
 * Hook to read tool input
 */
export function useToolInput() {
  return useOpenAiGlobal('toolInput');
}

/**
 * Hook to read tool output
 */
export function useToolOutput() {
  return useOpenAiGlobal('toolOutput');
}

/**
 * Hook to read current theme
 */
export function useTheme() {
  return useOpenAiGlobal('theme') ?? 'light';
}

/**
 * Hook to read current display mode
 */
export function useDisplayMode() {
  return useOpenAiGlobal('displayMode') ?? 'inline';
}

/**
 * Hook to manage widget state with persistence
 */
export function useWidgetState<T extends WidgetState>(
  defaultState: T | (() => T)
): readonly [T, (state: T | ((prev: T) => T)) => void] {
  const widgetStateFromWindow = useOpenAiGlobal('widgetState') as T | undefined;

  const [widgetState, _setWidgetState] = useState<T>(() => {
    if (widgetStateFromWindow != null) {
      return widgetStateFromWindow;
    }
    return typeof defaultState === 'function' ? defaultState() : defaultState;
  });

  // Sync with window state when it changes
  useEffect(() => {
    if (widgetStateFromWindow != null) {
      _setWidgetState(widgetStateFromWindow);
    }
  }, [widgetStateFromWindow]);

  const setWidgetState = useCallback(
    (state: T | ((prev: T) => T)) => {
      _setWidgetState((prevState) => {
        const newState = typeof state === 'function' ? state(prevState) : state;

        // Persist to ChatGPT host
        if (window.openai?.setWidgetState) {
          window.openai.setWidgetState(newState);
        }

        return newState;
      });
    },
    []
  );

  return [widgetState, setWidgetState] as const;
}

/**
 * Hook to call MCP tools
 */
export function useCallTool() {
  return useCallback(async (name: string, args: Record<string, unknown>) => {
    if (window.openai?.callTool) {
      await window.openai.callTool(name, args);
    } else {
      console.warn('window.openai.callTool not available');
    }
  }, []);
}

/**
 * Hook to upload files
 */
export function useFileUpload() {
  return useCallback(async (file: File) => {
    if (window.openai?.uploadFile) {
      return await window.openai.uploadFile(file);
    }
    throw new Error('window.openai.uploadFile not available');
  }, []);
}

/**
 * Hook to get file download URL
 */
export function useFileDownload() {
  return useCallback(async (fileId: string) => {
    if (window.openai?.getFileDownloadUrl) {
      return await window.openai.getFileDownloadUrl({ fileId });
    }
    throw new Error('window.openai.getFileDownloadUrl not available');
  }, []);
}

/**
 * Hook to request display mode changes
 */
export function useRequestDisplayMode() {
  return useCallback(async (mode: 'inline' | 'pip' | 'fullscreen') => {
    if (window.openai?.requestDisplayMode) {
      await window.openai.requestDisplayMode({ mode });
    }
  }, []);
}

/**
 * Hook to send follow-up messages
 */
export function useSendFollowUp() {
  return useCallback(async (prompt: string) => {
    if (window.openai?.sendFollowUpMessage) {
      await window.openai.sendFollowUpMessage({ prompt });
    }
  }, []);
}
