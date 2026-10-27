import type { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "join";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * `primary` is robin: the one main action on a screen. `secondary` is white on a grey lip. `join` is the
   * big robin button for joining a room, the one action every phone shares.
   */
  variant?: ButtonVariant;
  /** Fill the width of the container, for actions pinned to the bottom of a phone. */
  block?: boolean;
}

/** A pill button on a solid lip, 48px tall (60px to join). */
export function Button({
  variant = "primary",
  block = false,
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  const classes = [styles.button, styles[variant], block ? styles.block : "", className ?? ""].join(" ");
  return <button type={type} className={classes.trim()} {...rest} />;
}
