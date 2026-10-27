import { type ReactNode, useEffect, useRef } from "react";
import styles from "./Drawer.module.css";

interface DrawerProps {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

/** A panel from the right for the detail the main screen leaves out. A modal dialog, so Escape closes it. */
export function Drawer({ title, open, onClose, children }: DrawerProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className={styles.drawer} onClose={onClose} aria-labelledby="drawer-title">
      <header className={styles.head}>
        <h2 id="drawer-title" className={styles.title}>
          {title}
        </h2>
        <button type="button" className={styles.close} onClick={onClose}>
          Close
        </button>
      </header>
      <div className={styles.body}>{children}</div>
    </dialog>
  );
}
