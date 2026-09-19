import * as React from 'react';
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
 variant?: 'default'|'destructive'|'outline'|'secondary'|'ghost'|'link';
 size?:'default'|'sm'|'lg'|'icon';
 asChild?:boolean;
}
export const Button:React.ForwardRefExoticComponent<ButtonProps & React.RefAttributes<HTMLButtonElement>>;
export const buttonVariants:(props?:Record<string,unknown>)=>string;