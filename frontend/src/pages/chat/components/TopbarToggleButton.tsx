type Props = {
  topbarHidden: boolean;
  onToggle: () => void;
};

export function TopbarToggleButton({ topbarHidden, onToggle }: Props) {
  return (
    <button
      type="button"
      className="topbar-toggle-btn"
      onClick={onToggle}
      title={topbarHidden ? "显示顶部栏" : "隐藏顶部栏"}
      aria-label={topbarHidden ? "显示顶部栏" : "隐藏顶部栏"}
    >
      <span aria-hidden="true">⋮</span>
    </button>
  );
}
