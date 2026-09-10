/** Pull the backend's `{ detail: string }` message out of an axios error. */
export function apiErrorMessage(err: unknown, fallback = "Something went wrong."): string {
    if (
        typeof err === "object" &&
        err !== null &&
        "response" in err &&
        typeof (err as { response?: unknown }).response === "object"
    ) {
        const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
        if (typeof detail === "string" && detail) return detail;
    }
    return fallback;
}
