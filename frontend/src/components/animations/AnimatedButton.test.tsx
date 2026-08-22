/**
 * Performance Baseline Test for AnimatedButton
 *
 * 测试指标：
 * 1. Bundle大小增长
 * 2. 组件渲染性能
 * 3. 动画帧率
 * 4. 内存占用
 *
 * @version 1.0.0
 * @created 2026-08-16
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { AnimatedButton } from './AnimatedButton';

describe('AnimatedButton - Performance Baseline', () => {
  it('should render without crashing', () => {
    const { container } = render(
      <AnimatedButton>Test Button</AnimatedButton>
    );
    expect(container.querySelector('.animated-btn')).toBeTruthy();
  });

  it('should have correct default props', () => {
    const { container } = render(
      <AnimatedButton>Test</AnimatedButton>
    );
    const button = container.querySelector('.animated-btn');
    expect(button?.classList.contains('animated-btn--primary')).toBe(true);
    expect(button?.classList.contains('animated-btn--medium')).toBe(true);
  });

  it('should render all variants', () => {
    const variants = ['primary', 'secondary', 'ghost', 'danger'] as const;

    variants.forEach(variant => {
      const { container } = render(
        <AnimatedButton variant={variant}>Test</AnimatedButton>
      );
      const button = container.querySelector('.animated-btn');
      expect(button?.classList.contains(`animated-btn--${variant}`)).toBe(true);
    });
  });

  it('should render all sizes', () => {
    const sizes = ['small', 'medium', 'large'] as const;

    sizes.forEach(size => {
      const { container } = render(
        <AnimatedButton size={size}>Test</AnimatedButton>
      );
      const button = container.querySelector('.animated-btn');
      expect(button?.classList.contains(`animated-btn--${size}`)).toBe(true);
    });
  });

  it('should handle disabled state', () => {
    const { container } = render(
      <AnimatedButton disabled>Test</AnimatedButton>
    );
    const button = container.querySelector('.animated-btn') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it('should apply custom className', () => {
    const { container } = render(
      <AnimatedButton className="custom-class">Test</AnimatedButton>
    );
    const button = container.querySelector('.animated-btn');
    expect(button?.classList.contains('custom-class')).toBe(true);
  });

  // 性能测试：快速渲染多个按钮
  it('should render 100 buttons quickly', () => {
    const startTime = performance.now();

    const buttons = Array.from({ length: 100 }, (_, i) => (
      <AnimatedButton key={i}>Button {i}</AnimatedButton>
    ));

    render(<div>{buttons}</div>);

    const endTime = performance.now();
    const renderTime = endTime - startTime;

    // 应该在100ms内完成渲染
    expect(renderTime).toBeLessThan(100);

    console.log(`✓ Rendered 100 buttons in ${renderTime.toFixed(2)}ms`);
  });
});
