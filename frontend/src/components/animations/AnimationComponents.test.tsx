/**
 * Animation Components Tests
 * 测试所有动画组件的基础功能
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { AnimatedToast, ToastContainer } from './AnimatedToast';
import { Spinner } from './Spinner';
import { Skeleton, SkeletonText, SkeletonAvatar, SkeletonCard } from './Skeleton';

describe('AnimatedToast', () => {
  const mockToast = {
    id: 'test-1',
    message: 'Test message',
    type: 'info' as const,
  };

  it('should render toast with message', () => {
    const { container } = render(
      <AnimatedToast toast={mockToast} index={0} onClose={() => {}} />
    );
    expect(container.textContent).toContain('Test message');
  });

  it('should render all toast types', () => {
    const types = ['info', 'success', 'warning', 'error'] as const;

    types.forEach(type => {
      const { container } = render(
        <AnimatedToast
          toast={{ ...mockToast, type }}
          index={0}
          onClose={() => {}}
        />
      );
      expect(container.querySelector(`.animated-toast--${type}`)).toBeTruthy();
    });
  });

  it('should render ToastContainer with multiple toasts', () => {
    const toasts = [
      { id: '1', message: 'Toast 1', type: 'info' as const },
      { id: '2', message: 'Toast 2', type: 'success' as const },
    ];

    const { container } = render(
      <ToastContainer toasts={toasts} onClose={() => {}} />
    );

    expect(container.querySelectorAll('.animated-toast').length).toBe(2);
  });
});

describe('Spinner', () => {
  it('should render spinner', () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector('.spinner')).toBeTruthy();
  });

  it('should render all sizes', () => {
    const sizes = ['small', 'medium', 'large'] as const;

    sizes.forEach(size => {
      const { container } = render(<Spinner size={size} />);
      expect(container.querySelector(`.spinner--${size}`)).toBeTruthy();
    });
  });

  it('should render custom size', () => {
    const { container } = render(<Spinner size={48} />);
    const spinner = container.querySelector('.spinner') as HTMLElement;
    expect(spinner.style.width).toBe('48px');
  });

  it('should accept custom color', () => {
    const { container } = render(<Spinner color="#FF0000" />);
    const circle = container.querySelector('circle');
    expect(circle?.getAttribute('stroke')).toBe('#FF0000');
  });
});

describe('Skeleton', () => {
  it('should render skeleton', () => {
    const { container } = render(<Skeleton />);
    expect(container.querySelector('.skeleton')).toBeTruthy();
  });

  it('should render all variants', () => {
    const variants = ['text', 'circular', 'rectangular'] as const;

    variants.forEach(variant => {
      const { container } = render(<Skeleton variant={variant} />);
      expect(container.querySelector(`.skeleton--${variant}`)).toBeTruthy();
    });
  });

  it('should render SkeletonText with multiple lines', () => {
    const { container } = render(<SkeletonText lines={5} />);
    expect(container.querySelectorAll('.skeleton').length).toBe(5);
  });

  it('should render SkeletonAvatar', () => {
    const { container } = render(<SkeletonAvatar size={64} />);
    const skeleton = container.querySelector('.skeleton') as HTMLElement;
    expect(skeleton.style.width).toBe('64px');
    expect(skeleton.style.height).toBe('64px');
  });

  it('should render SkeletonCard', () => {
    const { container } = render(<SkeletonCard />);
    expect(container.querySelector('.skeleton-card')).toBeTruthy();
  });

  it('should support different animation types', () => {
    const animations = ['pulse', 'wave', 'none'] as const;

    animations.forEach(animation => {
      const { container } = render(<Skeleton animation={animation} />);
      expect(container.querySelector(`.skeleton--${animation}`)).toBeTruthy();
    });
  });
});

describe('Performance - Batch Rendering', () => {
  it('should render 50 spinners quickly', () => {
    const startTime = performance.now();

    const spinners = Array.from({ length: 50 }, (_, i) => (
      <Spinner key={i} />
    ));

    render(<div>{spinners}</div>);

    const endTime = performance.now();
    const renderTime = endTime - startTime;

    expect(renderTime).toBeLessThan(50);
    console.log(`✓ Rendered 50 spinners in ${renderTime.toFixed(2)}ms`);
  });

  it('should render 50 skeletons quickly', () => {
    const startTime = performance.now();

    const skeletons = Array.from({ length: 50 }, (_, i) => (
      <Skeleton key={i} />
    ));

    render(<div>{skeletons}</div>);

    const endTime = performance.now();
    const renderTime = endTime - startTime;

    expect(renderTime).toBeLessThan(50);
    console.log(`✓ Rendered 50 skeletons in ${renderTime.toFixed(2)}ms`);
  });
});
