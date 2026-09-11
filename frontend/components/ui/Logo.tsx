import { Waypoints } from "lucide-react";

export function Logo({ size = 8 }: { size?: number }) {
    return (
        <div
            className="grid place-items-center rounded-xl bg-accent text-accent-fg"
            style={{ width: `${size * 4}px`, height: `${size * 4}px` }}
        >
            <Waypoints size={size * 2.2} />
        </div>
    );
}
