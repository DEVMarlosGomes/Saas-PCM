import { HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

export function HelpTooltip({ text, side = "top" }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center justify-center w-4 h-4 rounded-full text-muted-foreground/50 hover:text-primary transition-colors align-middle ml-1 shrink-0"
          tabIndex={-1}
        >
          <HelpCircle className="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent side={side} className="max-w-[240px] text-center leading-snug text-xs">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}
