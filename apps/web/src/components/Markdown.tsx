import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders agent output as GitHub-flavored markdown. Agents answer with
 * headings, tables, and lists; rendering them keeps the assistant replies
 * readable. Text is treated as untrusted: links stay absolute-only and
 * there is no raw HTML.
 */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            // Only absolute http(s) links survive; relative schemes (javascript:, etc.) drop out.
            if (typeof href !== 'string' || !/^https?:\/\//i.test(href)) return <>{children}</>;
            return (
              <a href={href} target="_blank" rel="noreferrer noopener">
                {children}
              </a>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
