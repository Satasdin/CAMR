export { h, render, Fragment, createContext } from "preact";
export { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback, useContext } from "preact/hooks";
export { signal, computed, effect, batch, useSignal, useComputed, useSignalEffect } from "@preact/signals";
import htm from "htm";
import { h } from "preact";
export const html = htm.bind(h);
