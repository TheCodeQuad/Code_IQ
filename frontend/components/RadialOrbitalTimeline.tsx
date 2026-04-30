"use client";
import React, { useState, useEffect, useRef } from "react";
import { ArrowRight, Link as LinkIcon, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface TimelineItem {
  id: number;
  title: string;
  date: string;
  content: string;
  category: string;
  icon: React.ElementType;
  relatedIds: number[];
  status: "completed" | "in-progress" | "pending";
  energy: number;
}

interface RadialOrbitalTimelineProps {
  timelineData: TimelineItem[];
}

export default function RadialOrbitalTimeline({
  timelineData,
}: RadialOrbitalTimelineProps) {
  const [expandedItems, setExpandedItems] = useState<Record<number, boolean>>({});
  const [rotationAngle, setRotationAngle] = useState<number>(0);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [pulseEffect, setPulseEffect] = useState<Record<number, boolean>>({});
  const [centerOffset, setCenterOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [activeNodeId, setActiveNodeId] = useState<number | null>(null);
  const [autoCycle, setAutoCycle] = useState<boolean>(true);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const orbitRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const handleContainerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === containerRef.current || e.target === orbitRef.current) {
      setExpandedItems({});
      setActiveNodeId(null);
      setPulseEffect({});
      setAutoRotate(true);
      setAutoCycle(true);
    }
  };

  const toggleItem = (id: number) => {
    setExpandedItems((prev) => {
      const newState = { ...prev };
      Object.keys(newState).forEach((key) => {
        if (parseInt(key) !== id) {
          newState[parseInt(key)] = false;
        }
      });

      newState[id] = !prev[id];

      if (!prev[id]) {
        setActiveNodeId(id);
        setAutoRotate(false);
        setAutoCycle(false);

        const relatedItems = getRelatedItems(id);
        const newPulseEffect: Record<number, boolean> = {};
        relatedItems.forEach((relId) => {
          newPulseEffect[relId] = true;
        });
        setPulseEffect(newPulseEffect);

        centerViewOnNode(id);
      } else {
        setActiveNodeId(null);
        setAutoRotate(true);
        setAutoCycle(true);
        setPulseEffect({});
      }

      return newState;
    });
  };

  useEffect(() => {
    let rotationTimer: NodeJS.Timeout;

    if (autoRotate) {
      rotationTimer = setInterval(() => {
        setRotationAngle((prev) => parseFloat(((prev + 0.1) % 360).toFixed(3)));
      }, 50);
    }

    return () => {
      if (rotationTimer) clearInterval(rotationTimer);
    };
  }, [autoRotate]);

  const centerViewOnNode = React.useCallback((nodeId: number) => {
    const nodeIndex = timelineData.findIndex((item) => item.id === nodeId);
    if (nodeIndex === -1) return;
    const totalNodes = timelineData.length;
    const targetAngle = (nodeIndex / totalNodes) * 360;
    setRotationAngle(270 - targetAngle);
  }, [timelineData]);

  const openItem = React.useCallback((id: number) => {
    setExpandedItems({ [id]: true });
    setActiveNodeId(id);
    setAutoRotate(true); // Maintain the spinning orbital effect automatically

    const currentItem = timelineData.find((item) => item.id === id);
    const relatedItems = currentItem ? currentItem.relatedIds : [];
    const newPulseEffect: Record<number, boolean> = {};
    relatedItems.forEach((relId) => {
      newPulseEffect[relId] = true;
    });
    setPulseEffect(newPulseEffect);
  }, [timelineData]);

  const activeNodeIdRef = useRef<number | null>(activeNodeId);
  useEffect(() => {
    activeNodeIdRef.current = activeNodeId;
  }, [activeNodeId]);

  useEffect(() => {
    let cycleInterval: NodeJS.Timeout;

    // Immediately open the first item if nothing is active
    if (autoCycle && timelineData.length > 0 && activeNodeIdRef.current === null) {
      openItem(timelineData[0].id);
    }

    if (autoCycle && timelineData.length > 0) {
      cycleInterval = setInterval(() => {
        const currentActive = activeNodeIdRef.current;
        const currentIndex = currentActive === null ? -1 : timelineData.findIndex((item) => item.id === currentActive);
        const nextIndex = (currentIndex + 1) % timelineData.length;
        const nextId = timelineData[nextIndex].id;
        
        openItem(nextId);
      }, 1000); // 4 seconds interval
    }

    return () => {
      if (cycleInterval) clearInterval(cycleInterval);
    };
  }, [autoCycle, timelineData, openItem]);

  const calculateNodePosition = (index: number, total: number) => {
    const angle = ((index / total) * 360 + rotationAngle) % 360;
    const radius = 220; // Slightly larger radius for a more spacious feel
    const radian = (angle * Math.PI) / 180;

    const x = radius * Math.cos(radian) + centerOffset.x;
    const y = radius * Math.sin(radian) + centerOffset.y;

    const zIndex = Math.round(100 + 50 * Math.cos(radian));
    const opacity = Math.max(0.3, Math.min(1, 0.4 + 0.6 * ((1 + Math.sin(radian)) / 2)));

    return { x, y, angle, zIndex, opacity };
  };

  const getRelatedItems = (itemId: number): number[] => {
    const currentItem = timelineData.find((item) => item.id === itemId);
    return currentItem ? currentItem.relatedIds : [];
  };

  const isRelatedToActive = (itemId: number): boolean => {
    if (!activeNodeId) return false;
    const relatedItems = getRelatedItems(activeNodeId);
    return relatedItems.includes(itemId);
  };

  const getStatusStyles = (status: TimelineItem["status"]): string => {
    switch (status) {
      case "completed":
        return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
      case "in-progress":
        return "bg-blue-500/10 text-blue-600 border-blue-500/20";
      case "pending":
        return "bg-muted text-muted-foreground border-border";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <div className="w-full py-16 font-sans relative flex justify-center px-4 md:px-8">
      {/* Outer wrapper to contain the distinct shape */}
      <div className="relative w-full max-w-7xl h-[650px] flex items-center rounded-[40px] md:rounded-[100px] overflow-visible mx-auto"
           style={{
             background: "linear-gradient(90deg, #F8DBE4 0%, #FAe5eb 30%, #F5E1F0 100%)",
             boxShadow: "0 20px 40px -15px rgba(0,0,0,0.05)"
           }}>
        
        {/* Two-column layout grid */}
        <div className="w-full h-full grid grid-cols-1 md:grid-cols-2 z-10" ref={containerRef} onClick={handleContainerClick}>
          
          {/* Left Column: Text Formatting */}
          <div className="flex flex-col justify-center px-12 md:pl-24 lg:pl-32 pr-4 z-20 text-black">
            <h3 className="text-xl md:text-2xl text-black/80 font-medium mb-3">
              How it works
            </h3>
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 tracking-tight">
              From Code to Docs
            </h2>
            <p className="text-lg md:text-xl text-black/70 max-w-md font-medium leading-relaxed">
              Watch your code transform through our five-stage agentic pipeline
            </p>
          </div>

          {/* Right Column: Orbital Timeline */}
          <div className="relative w-full h-full flex items-center justify-center" suppressHydrationWarning>
            <div
              className="absolute w-full h-full flex items-center justify-center transition-transform duration-1000 ease-out"
              ref={orbitRef}
              style={{ perspective: "1000px" }}
              suppressHydrationWarning
            >
              {/* Central Core */}
              <div className="absolute w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center z-10 shadow-sm border border-emerald-100" suppressHydrationWarning>
                <div className="absolute w-20 h-20 rounded-full border border-emerald-200/50 animate-ping opacity-70" />
                <div className="absolute w-28 h-28 rounded-full border border-emerald-100/50 animate-ping opacity-50" style={{ animationDelay: "0.5s" }} />
                <div className="w-12 h-12 rounded-full bg-[#18C982] backdrop-blur-md shadow-inner flex items-center justify-center">
                  <Zap className="text-white w-5 h-5" />
                </div>
              </div>

              {/* Orbit rings (Changed to dark/black lines as requested) */}
              <div className="absolute w-[440px] h-[440px] rounded-full border border-black/10 border-dashed" suppressHydrationWarning />
              <div className="absolute w-[300px] h-[300px] rounded-full border border-black/5" suppressHydrationWarning />

          {timelineData.map((item, index) => {
            const position = calculateNodePosition(index, timelineData.length);
            const isExpanded = expandedItems[item.id];
            const isRelated = isRelatedToActive(item.id);
            const isPulsing = pulseEffect[item.id];
            const Icon = item.icon;

            const nodeStyle = {
              transform: `translate(${position.x}px, ${position.y}px)`,
              zIndex: isExpanded ? 200 : position.zIndex,
              opacity: isExpanded ? 1 : position.opacity,
            };

            return (
              <div
                key={item.id}
                ref={(el) => (nodeRefs.current[item.id] = el)}
                className="absolute transition-all duration-700 cursor-pointer flex flex-col items-center"
                style={nodeStyle}
                suppressHydrationWarning
                onClick={(e) => {
                  e.stopPropagation();
                  toggleItem(item.id);
                }}
              >
                {/* Node highlight/pulse */}
                <div
                  className={`absolute rounded-full -inset-2 transition-opacity duration-300 ${
                    isPulsing ? "opacity-100 animate-pulse bg-emerald-100/50" : "opacity-0"
                  }`}
                  style={{
                    width: '64px',
                    height: '64px',
                    left: '-8px',
                    top: '-8px',
                  }}
                  suppressHydrationWarning
                />

                {/* Node Circle */}
                <div
                  className={`
                  relative z-10 w-12 h-12 rounded-full flex items-center justify-center
                  border-2 transition-all duration-300 transform shadow-sm
                  ${
                    isExpanded
                      ? "bg-emerald-500 text-white border-emerald-600 scale-125 shadow-emerald-200"
                      : isRelated
                      ? "bg-white text-emerald-600 border-emerald-300 animate-pulse"
                      : "bg-white text-muted-foreground border-border hover:border-emerald-300 hover:text-emerald-500"
                  }
                `}
                  suppressHydrationWarning
                >
                  <Icon size={20} />
                </div>

                {/* Node Label (when not expanded) */}
                <div
                  className={`
                  absolute top-14 whitespace-nowrap text-sm font-medium
                  transition-all duration-300 tracking-wide
                  ${isExpanded ? "opacity-0" : "text-foreground opacity-100"}
                  ${position.opacity < 0.6 ? "opacity-0" : ""}
                `}
                  suppressHydrationWarning
                >
                  {item.title}
                </div>

                {/* Expanded Card */}
                {isExpanded && (
                  <Card className="absolute top-16 left-1/2 -translate-x-1/2 w-72 bg-card border-border shadow-xl z-50">
                    <CardHeader className="pb-2">
                      <div className="flex justify-between items-center">
                        <Badge variant="outline" className={`px-2 py-0 h-5 text-[10px] uppercase font-bold tracking-wider rounded ${getStatusStyles(item.status)}`}>
                          {item.status.replace("-", " ")}
                        </Badge>
                        <span className="text-xs font-mono text-muted-foreground">
                          {item.date}
                        </span>
                      </div>
                      <CardTitle className="text-base font-semibold mt-2 text-foreground">
                        {item.title}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground pb-4">
                      <p>{item.content}</p>

                      <div className="mt-4 pt-3 border-t border-border">
                        <div className="flex justify-between items-center text-xs mb-1">
                          <span className="flex items-center text-foreground font-medium">
                            <Zap size={12} className="mr-1 text-emerald-500" />
                            Compute Energy
                          </span>
                          <span className="font-mono text-emerald-600 font-semibold">{item.energy}%</span>
                        </div>
                        <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 transition-all duration-1000"
                            style={{ width: `${item.energy}%` }}
                          />
                        </div>
                      </div>

                      {item.relatedIds.length > 0 && (
                        <div className="mt-4 pt-3 border-t border-border">
                          <div className="flex items-center mb-2">
                            <LinkIcon size={12} className="text-muted-foreground mr-1.5" />
                            <h4 className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
                              Connected Nodes
                            </h4>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {item.relatedIds.map((relatedId) => {
                              const relatedItem = timelineData.find((i) => i.id === relatedId);
                              return (
                                <Button
                                  key={relatedId}
                                  variant="secondary"
                                  size="sm"
                                  className="h-6 px-2 py-0 text-xs rounded-md bg-secondary text-secondary-foreground hover:bg-emerald-50 hover:text-emerald-700 transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleItem(relatedId);
                                  }}
                                >
                                  {relatedItem?.title}
                                  <ArrowRight size={10} className="ml-1 opacity-70" />
                                </Button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  </div>
</div>
  );
}