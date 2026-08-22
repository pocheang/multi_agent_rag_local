import React from 'react';

interface ImagePreviewProps {
  src: string;
  description: string;
  ocrText?: string;
  alt?: string;
}

/**
 * Component for previewing images with descriptions and OCR text
 */
export const ImagePreview: React.FC<ImagePreviewProps> = ({
  src,
  description,
  ocrText,
  alt = 'Image preview',
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <div className="image-preview border rounded-lg p-4 my-4 bg-gray-50 dark:bg-gray-800">
      <div className="flex flex-col space-y-3">
        {/* Image */}
        <div className="relative">
          <img
            src={src}
            alt={alt}
            className={`rounded-md w-full object-contain cursor-pointer transition-all ${
              isExpanded ? 'max-h-[600px]' : 'max-h-[300px]'
            }`}
            onClick={() => setIsExpanded(!isExpanded)}
          />
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="absolute top-2 right-2 bg-white dark:bg-gray-700 px-3 py-1 rounded-md shadow-md text-sm"
          >
            {isExpanded ? '收起' : '展开'}
          </button>
        </div>

        {/* Description */}
        <div className="text-sm">
          <span className="font-semibold text-gray-700 dark:text-gray-300">
            图片描述：
          </span>
          <p className="mt-1 text-gray-600 dark:text-gray-400">{description}</p>
        </div>

        {/* OCR Text (if available) */}
        {ocrText && (
          <div className="text-sm border-t pt-3">
            <span className="font-semibold text-gray-700 dark:text-gray-300">
              识别文字：
            </span>
            <p className="mt-1 text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
              {ocrText}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImagePreview;
