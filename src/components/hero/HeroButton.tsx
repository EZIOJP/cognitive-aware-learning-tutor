import { Button } from "../../app/components/ui/button";
import { cn } from "../../app/components/ui/utils";
import { useTheme } from "../../context/ThemeContext";

type HeroButtonProps = React.ComponentProps<typeof Button>;

/** Preview / opt-in hero button — applies toolkit variant classes */
export function HeroButton({ className, ...props }: HeroButtonProps) {
  const { buttonVariant } = useTheme();
  const variantClass =
    buttonVariant !== "default" ? `hero-btn-${buttonVariant}` : "";

  return (
    <Button
      className={cn("hero-styled", variantClass, className)}
      {...props}
    />
  );
}
